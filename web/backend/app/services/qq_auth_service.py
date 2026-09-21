"""QQ 登录（QQ 互联 OAuth2.0，server-side 模式）。

官方文档：https://wiki.connect.qq.com/开发攻略_server-side

── 两个必须知道的返回格式坑（照 JSON 解析会直接崩）──

腾讯这三个接口的返回格式**各不相同**，且都不是标准 JSON：

  1. /oauth2.0/token   → **URL 编码串**：access_token=xxx&expires_in=7776000&refresh_token=yyy
                          出错时同样是 URL 编码：code=100010&msg=...
  2. /oauth2.0/me      → **JSONP 包壳**：callback( {"client_id":"...","openid":"..."} );
                          必须先剥掉 callback( ) 外壳再解析
  3. /user/get_user_info → 这个才是纯 JSON：{"ret":0,"msg":"","nickname":"..."}

所以下面三处各写了各自的解析，不能共用一个 response.json()。

── openid 的作用域 ──

openid 是 **appid 维度**的：同一个 QQ 用户在不同应用下 openid 不同。所以
UserIdentity 的唯一键是 (provider, provider_uid) 而不是单独的 provider_uid。

── 没有邮箱怎么办 ──

QQ 授权拿不到邮箱（腾讯不提供）。按产品决定：先让人登录进来能用，后续在
报告页提示补邮箱——复用游客那套「绑定邮箱」机制。所以这里建号时给一个
**合成占位邮箱** qq-{openid}@qq.local，并标记 is_guest=True 让绑定横幅出现。

is_guest 在这里的语义是"这个账号还没有能收信的真邮箱、丢了找不回"，
与 CDK 游客同一个含义，所以复用同一个标记而不是新加一列——绑定邮箱后
两者都会被 guest_service.bind_email 置回 False，走的是同一条转正路径。
"""

import hashlib
import hmac
import secrets
import time
from typing import Optional, Tuple
from urllib.parse import parse_qs, quote, urlencode

import httpx

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import create_token, decode_token, hash_password
from app.models import User, UserIdentity

PROVIDER = "qq"

AUTHORIZE_URL = "https://graph.qq.com/oauth2.0/authorize"
TOKEN_URL = "https://graph.qq.com/oauth2.0/token"
OPENID_URL = "https://graph.qq.com/oauth2.0/me"
USERINFO_URL = "https://graph.qq.com/user/get_user_info"

# state 的有效期。它只需要覆盖"用户在腾讯授权页停留的时间"，给 10 分钟足够；
# 太长会让一个被截获的 state 有更久的可用窗口。
STATE_TTL_SECONDS = 600

# 拿到 code 之后换 JWT 的一次性令牌有效期。前端拿到就立刻兑换，30 秒绰绰有余。
HANDOFF_TTL_SECONDS = 30

_HTTP_TIMEOUT = 10.0


class QQAuthError(Exception):
    """QQ 登录链路上的任何失败。message 会被如实带到前端提示里——
    静默失败会让用户在登录页反复点击而不知道发生了什么。"""


def _require_enabled() -> None:
    if not settings.qq_login_enabled:
        raise QQAuthError("QQ 登录未配置（需要 AL_QQ_APP_ID / AL_QQ_APP_KEY / AL_QQ_REDIRECT_URI）")


# ---------------- state：防 CSRF，绑定到发起登录的那个浏览器 ----------------
#
# 只签一个短时效 JWT 是**不够**的，这是上一版的实际漏洞：那样的 state 只证明
# "这串东西是我们自己在 10 分钟内签发的"，而 /auth/qq/authorize 不需要登录，
# 任何人都能去要一个。攻击路径是登录态固定（login CSRF）：
#   1. 攻击者自己走一遍 /authorize，用**自己的 QQ 号**在腾讯那边完成授权；
#   2. 在回调落地前把自己的 code 截下来（回调是 GET，地址栏里就有）；
#   3. 把 .../auth/qq/callback?code=<攻击者的>&state=<攻击者的> 发给受害者；
#   4. 受害者的浏览器完成兑换，于是**受害者登录进了攻击者的账号**——
#      他之后上传的每一份材料、每一条评审，攻击者登进自己账号就能看。
#
# 修法是把 state 绑定到发起授权的那个浏览器：授权时生成一个随机 nonce，
#   · state 里放它的 **SHA-256 摘要**（state 会经过腾讯、进浏览器历史和日志，
#     放原文等于把绑定用的秘密也一起公开了）；
#   · nonce 原文只写进一个 HttpOnly + SameSite=Lax 的 Cookie。
# 回调时两边必须对得上。攻击者无法在受害者的浏览器里种下我们域名的 Cookie，
# 上面那条链在第 4 步就断了。
#
# 单次使用：回调（无论成败）都会**删掉这个 Cookie**，也就是绑定用的那半边秘密
# 当场销毁。于是同一个 state 在同一个浏览器里第二次回调必然失败（Cookie 没了），
# 在别的浏览器里从来就没成功过。这是本仓库现有机制能给到的单次语义，且天然
# 多 worker 安全（状态在浏览器里，不在进程内存）；做成 DB 行需要在**未登录**
# 的 /authorize 上为每次点击写一行，而 auth_tokens.user_id 是 NOT NULL + 外键，
# 此刻还没有 user 可挂。取舍写在这里，见交接说明。

STATE_COOKIE_NAME = "al_qq_state"


def _nonce_digest(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("utf-8")).hexdigest()


def issue_state() -> Tuple[str, str]:
    """返回 (state, nonce)。state 放进授权地址，nonce 放进 HttpOnly Cookie。"""
    nonce = secrets.token_urlsafe(24)
    state = create_token(
        f"qq-state:{_nonce_digest(nonce)}", settings.jwt_secret, STATE_TTL_SECONDS
    )
    return state, nonce


def verify_state(state: str, nonce: str) -> bool:
    """state 必须是我们签的、没过期，**并且**与这个浏览器 Cookie 里的 nonce 配对。

    nonce 为空（Cookie 丢了 / 从没有过 / 已经被上一次回调清掉）一律判假：
    这正是挡住"攻击者构造的回调 URL"的那一刀，不能因为"用户 Cookie 可能被
    浏览器策略挡掉"就放宽——放宽等于整道防护不存在。
    """
    if not state or not nonce:
        return False
    try:
        payload = decode_token(state, settings.jwt_secret)
    except ValueError:
        return False
    subject = str(payload.get("sub", ""))
    if not subject.startswith("qq-state:"):
        return False
    return hmac.compare_digest(subject[len("qq-state:"):], _nonce_digest(nonce))


def state_cookie_is_secure() -> bool:
    """站点跑在 https 上就给 Cookie 加 Secure。

    判据取 settings.public_web_url —— 与 config.looks_like_production /
    邮件链接用的是同一个"本站对外地址"字段。本地开发是 http://localhost:5199，
    此时**不能**加 Secure：加了浏览器根本不会回传这个 Cookie，表现是
    "本地 QQ 登录永远校验失败"，而错误信息只会说"授权状态校验失败"。
    """
    return settings.public_web_url.strip().lower().startswith("https://")


def set_state_cookie(response, nonce: str) -> None:
    """把 nonce 种进浏览器。HttpOnly：JS 读不到，XSS 也偷不走这半边秘密。

    SameSite=Lax 而不是 Strict：回调是腾讯 302 过来的**跨站顶层导航**，
    Strict 时浏览器不会带上这个 Cookie，整条登录链会当场断掉（Lax 恰好允许
    顶层 GET 导航携带，这也正是 OAuth 回调需要的最小放宽）。
    """
    response.set_cookie(
        STATE_COOKIE_NAME,
        nonce,
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=state_cookie_is_secure(),
        path="/",
    )


def clear_state_cookie(response) -> None:
    """回调结束（成功或失败都要）删掉它——这就是 state 的"用一次即废"。"""
    response.delete_cookie(STATE_COOKIE_NAME, path="/")


# ---------------- 第 1 步：授权地址 ----------------

def build_authorize_url(state: str) -> str:
    _require_enabled()
    # redirect_uri 必须与 QQ 互联后台登记的**逐字符一致**，否则 100010。
    # 所以直接用配置里那一串，不做任何规范化（不补/删尾斜杠、不改大小写）。
    params = {
        "response_type": "code",
        "client_id": settings.qq_app_id,
        "redirect_uri": settings.qq_redirect_uri,
        "state": state,
        "scope": "get_user_info",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params, quote_via=quote)}"


# ---------------- 第 2 步：code 换 access_token ----------------

def _parse_urlencoded(body: str) -> dict:
    """腾讯的 token 接口返回 URL 编码串而不是 JSON。parse_qs 的值是 list，
    这里压平成单值——所有字段都只会出现一次。"""
    return {k: v[0] for k, v in parse_qs(body.strip()).items() if v}


def exchange_code_for_token(code: str) -> str:
    _require_enabled()
    params = {
        "grant_type": "authorization_code",
        "client_id": settings.qq_app_id,
        "client_secret": settings.qq_app_key,
        "code": code,
        "redirect_uri": settings.qq_redirect_uri,
    }
    try:
        resp = httpx.get(TOKEN_URL, params=params, timeout=_HTTP_TIMEOUT)
    except httpx.HTTPError as exc:
        raise QQAuthError(f"连接 QQ 服务器失败：{exc}") from exc

    data = _parse_urlencoded(resp.text)
    token = data.get("access_token")
    if not token:
        # 失败时腾讯同样返回 URL 编码：code=100010&msg=redirect uri is illegal
        raise QQAuthError(
            f"QQ 换取令牌失败（{data.get('code', '未知')}）：{data.get('msg') or resp.text[:200]}"
        )
    return token


# ---------------- 第 3 步：取 openid ----------------

def _strip_jsonp(body: str) -> str:
    """剥掉 callback( ... ); 外壳。腾讯这个接口只给 JSONP，没有 fmt=json。"""
    body = body.strip()
    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1 or end < start:
        return ""
    return body[start : end + 1]


def fetch_openid(access_token: str) -> str:
    import json as _json

    try:
        resp = httpx.get(OPENID_URL, params={"access_token": access_token}, timeout=_HTTP_TIMEOUT)
    except httpx.HTTPError as exc:
        raise QQAuthError(f"连接 QQ 服务器失败：{exc}") from exc

    raw = _strip_jsonp(resp.text)
    if not raw:
        raise QQAuthError(f"QQ 返回了无法解析的 openid 响应：{resp.text[:200]}")
    try:
        data = _json.loads(raw)
    except ValueError as exc:
        raise QQAuthError(f"QQ 的 openid 响应不是合法 JSON：{raw[:200]}") from exc

    openid = data.get("openid")
    if not openid:
        raise QQAuthError(f"QQ 未返回 openid：{data.get('error_description') or raw[:200]}")
    return openid


def fetch_nickname(access_token: str, openid: str) -> Optional[str]:
    """取昵称。这一步**失败不阻断登录**——昵称只是显示名，
    为了一个装饰性字段把人挡在门外是本末倒置。"""
    try:
        resp = httpx.get(
            USERINFO_URL,
            params={
                "access_token": access_token,
                "oauth_consumer_key": settings.qq_app_id,
                "openid": openid,
            },
            timeout=_HTTP_TIMEOUT,
        )
        data = resp.json()  # 这个接口是纯 JSON（与上面两个不同）
    except Exception:
        return None
    if data.get("ret") != 0:
        return None
    nickname = (data.get("nickname") or "").strip()
    return nickname or None


# ---------------- 落库：找到或创建账号 ----------------

def _existing_by_openid(db: Session, openid: str) -> Optional[User]:
    identity = (
        db.query(UserIdentity)
        .filter(UserIdentity.provider == PROVIDER, UserIdentity.provider_uid == openid)
        .first()
    )
    if identity is None:
        return None
    return db.query(User).filter(User.id == identity.user_id).first()


def find_or_create_user(db: Session, openid: str, nickname: Optional[str]) -> Tuple[User, bool]:
    """返回 (账号, 是否新建)。"""
    identity = (
        db.query(UserIdentity)
        .filter(UserIdentity.provider == PROVIDER, UserIdentity.provider_uid == openid)
        .first()
    )
    if identity is not None:
        user = db.query(User).filter(User.id == identity.user_id).first()
        if user is not None:
            return user, False
        # 映射还在但账号没了（删号漏了这张表）——把孤儿映射清掉重建，
        # 不然这个 QQ 号会永远登不进来且没有任何提示。
        db.delete(identity)
        db.commit()

    user = User(
        # 合成占位邮箱：QQ 不提供邮箱。见文件头说明。
        email=f"qq-{openid}@qq.local",
        password_hash=hash_password(secrets.token_urlsafe(32)),  # 不可用密码登录
        display_name=nickname or "QQ 用户",
        # "还没有能收信的真邮箱" —— 与 CDK 游客同一含义，复用同一个标记，
        # 让报告页的绑定邮箱横幅出现，绑定后由 guest_service.bind_email 置回 False。
        is_guest=True,
    )
    db.add(user)
    try:
        db.flush()
        db.add(
            UserIdentity(
                user_id=user.id,
                provider=PROVIDER,
                provider_uid=openid,
                nickname=nickname,
            )
        )
        db.commit()
    except IntegrityError:
        # 同一个 QQ 号在两个标签页同时首次登录：两个请求都查不到映射、
        # 都走到这里建号，第二个撞上 users.email 或 (provider, provider_uid)
        # 的唯一约束。不捕获就是 500 —— 而用户什么也没做错，正确结果是
        # "回到已经被另一个请求建好的那个账号"，不是报错也不是再建一个。
        db.rollback()
        existing = _existing_by_openid(db, openid)
        if existing is None:
            raise QQAuthError("账号创建冲突，请重新发起 QQ 登录")
        return existing, False
    db.refresh(user)
    return user, True
