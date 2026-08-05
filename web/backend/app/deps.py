"""依赖注入：所有链路的入口守卫都在这里，路由只管业务。

一条评审请求要过的关卡（顺序即依赖顺序）：
    rate_limit → current_identity → resolve_llm_key → check_quota
每一关都可通过 app/config.py 的开关独立启停。
"""

import hashlib
import hmac
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AdminDisabled, RateLimited, Unauthorized
from app.core.logging import logger
from app.core.ratelimit import get_limiter
from app.core.security import decode_token
from app.db import get_db
from app.models import User
from app.services import admin_settings_service, key_service

# scope -> 不传 limit 时该读哪个旋钮（settings 属性名 == 后台设置项键名）。
# 没登记的 scope 回落通用的「每分钟」上限。
#
# 为什么需要这张表：评审路由是 rate_limit("review", None, 3600)，
# limit 为 None 时曾无条件回落 ratelimit_per_minute —— 但窗口是 3600 秒，
# 于是「通用接口限流（次/分钟）」这一个数字实际同时决定了每个用户每小时
# 能发起多少次评审（全走平台垫付 key），而 AL_RATELIMIT_REVIEW_PER_HOUR
# 是个从没被读过的死变量。现在两个旋钮各管各的。
_SCOPE_LIMIT_SETTINGS = {
    "review": "ratelimit_review_per_hour",
}

# ---- 后台令牌爆破防护 ----
# /api/admin/* 用的是静态共享密钥，没有有效期也没有账号锁定，
# 唯一能挡住离线枚举的就是失败计数。按来源 IP 记；
# 反代后所有请求同一个 peer IP —— 那就退化成全局失败计数，
# 仍然能挡住枚举，代价是攻击者可以让管理员一起被锁 5 分钟（可接受：锁定会自动过期）。
ADMIN_AUTH_MAX_FAILURES = 10
ADMIN_AUTH_WINDOW_SECONDS = 300.0
_admin_auth_lock = threading.Lock()
_admin_auth_failures: dict = {}  # client_key -> [失败次数, 窗口起点]


class SessionExpired(Unauthorized):
    """带了令牌、但它已失效（过期 / 签名不对 / 密码改过 / 账号停用）。

    和「压根没登录」必须是两种东西。此前二者都被 optional_identity 悄悄
    抹成同一个匿名身份，用户看到的是：新发起的评审归属变成 anonymous、
    报告被匿名门禁裁剪、历史列表空了——而全程没有任何一条错误提示，
    表现得像"我的东西自己不见了"。
    code 单独给一个值，前端可以据此清掉本地 token 并提示"登录已过期"，
    而不用去猜一个笼统的 401 是"没登录"还是"登录烂了"。
    """

    code = "session_expired"
    message = "登录已过期，请重新登录"


# 密码重置后作废旧 JWT 用的标记行：写进 auth_tokens 表，purpose 取这个值。
#
# 为什么用一行"假令牌"而不是给 users 加一列 password_changed_at：
# 自签 JWT 一旦发出去就无法撤回（只认签名和 exp），改密码不留痕的话，
# 攻击者手上那把在改密码前偷到的 token 最长还能再用 7 天——"改密码"
# 这个动作对已经发生的入侵完全无效。要撤回就必须有服务端状态。
# 加列需要改 app/models（本轮不归我改，见交接说明），而 auth_tokens 本来
# 就是"认证令牌的服务端状态"表，语义最近：这行不是给谁用的令牌
# （token_hash 是随机值的摘要，没有任何人持有对应原文，也不会被 consume
# 命中——consume 按 purpose 过滤），它只承载一个事实：created_at 之前
# 签发的 JWT 全部作废。
SESSION_REVOKE_PURPOSE = "session_revoke"


class Identity:
    """统一身份对象：匿名与登录用户走同一套下游逻辑。"""

    def __init__(self, user_id: str, email: Optional[str] = None, plan: str = "free",
                 is_anonymous: bool = True, session_expired: bool = False,
                 display_name: Optional[str] = None):
        self.user_id = user_id
        self.email = email
        self.plan = plan
        self.is_anonymous = is_anonymous
        # 昵称之前不在这里：/auth/me 不返回它，前端于是既显示不出当前昵称、
        # 改完也无从确认改成功了。匿名身份没有昵称，保持 None。
        self.display_name = display_name
        # 只有 probe_identity（/auth/me）会把它置真：那条路不 401，
        # 但必须如实告诉前端"你带来的令牌被拒了"，否则又回到静默降级。
        self.session_expired = session_expired

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "plan": self.plan,
            "is_anonymous": self.is_anonymous,
            "session_expired": self.session_expired,
        }


def _client_key(request: Request, identity_id: str = None) -> str:
    if identity_id and identity_id != settings.anonymous_user_id:
        return f"user:{identity_id}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization 头里取出 Bearer 令牌；没带 / 不是 Bearer / 空串都返回 None。

    「没带令牌」和「带了个坏令牌」的分界线就在这里，下游全靠它区分两种情况。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip() or None


def sessions_revoked_at(db: Session, user_id: str) -> Optional[int]:
    """该用户"此刻之前签发的 JWT 全部作废"的时间点（epoch 整秒）；没有则 None。

    见 SESSION_REVOKE_PURPOSE 的说明。代价老实说：每个带令牌的请求多一次
    索引查询（auth_tokens.user_id / purpose 都有索引），换 JWT 可撤回。

    为什么向下取整到秒：JWT 的 iat 只有整秒精度。若拿带微秒的时间点去比，
    "重置于 10.4 秒、重置完立刻登录拿到 iat=10 的新令牌"会被判成
    10 < 10.4 即刻作废——用户改完密码根本登不进去。代价是与重置发生在
    同一秒内签发的令牌逃过一劫（≤1 秒的窗口），比登不进去可接受得多。
    """
    from app.models import AuthToken

    row = (
        db.query(AuthToken)
        .filter(AuthToken.user_id == user_id, AuthToken.purpose == SESSION_REVOKE_PURPOSE)
        .order_by(AuthToken.created_at.desc())
        .first()
    )
    if row is None or row.created_at is None:
        return None
    created_at = row.created_at
    if created_at.tzinfo is None:  # SQLite 取回来是 naive，补上 UTC 再比（同 auth_token_service）
        created_at = created_at.replace(tzinfo=timezone.utc)
    return int(created_at.timestamp())


def revoke_user_sessions(db: Session, user_id: str) -> None:
    """作废该用户当前已签发的全部 JWT。改密码后必须调，否则旧令牌还能用满 TTL。

    这里自己 commit：调用方（密码重置）刚把新的 password_hash 写进同一个 session，
    两件事必须一起落库——"密码改了但旧会话还活着"这个中间态一秒都不该存在。
    """
    from app.models import AuthToken

    now = datetime.now(timezone.utc)
    db.add(
        AuthToken(
            user_id=user_id,
            purpose=SESSION_REVOKE_PURPOSE,
            # 随机摘要：没有任何人持有对应原文，这行永远不会被当成可用令牌
            token_hash=hashlib.sha256(os.urandom(32)).hexdigest(),
            # 标记行不该被任何"清理过期令牌"的逻辑当垃圾扫掉——它一旦消失，
            # 被作废的旧 JWT 就会重新变得有效。给一个远期时间，语义上也成立：
            # 作废声明的有效期至少要覆盖 JWT 自己的 TTL。
            expires_at=now + timedelta(seconds=max(settings.jwt_ttl_seconds, 86400) * 10),
        )
    )
    db.commit()


async def current_identity(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Identity:
    """身份解析（埋线）。

    AL_AUTH_ENABLED=false（默认）：一律匿名，无需登录 —— 开源单机形态。
    AL_AUTH_ENABLED=true：必须带 Bearer token，否则 401。
    """
    if not settings.auth_enabled:
        return Identity(user_id=settings.anonymous_user_id, is_anonymous=True)

    token = bearer_token(authorization)
    if token is None:
        raise Unauthorized()

    try:
        payload = decode_token(token, settings.jwt_secret)
    except ValueError as exc:
        raise SessionExpired(str(exc))

    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise SessionExpired("用户不存在或已停用")

    # 改过密码就作废改密码之前签发的令牌——JWT 无状态，不查这一下的话
    # 被偷走的旧令牌在改完密码后还能继续用满 TTL（默认 7 天）。
    revoked_at = sessions_revoked_at(db, user.id)
    if revoked_at is not None and int(payload.get("iat") or 0) < revoked_at:
        raise SessionExpired("密码已修改，请用新密码重新登录")

    return Identity(
        user_id=user.id,
        email=user.email,
        plan=user.plan,
        is_anonymous=False,
        display_name=user.display_name,
    )


async def optional_identity(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Identity:
    """不强制登录的接口用（列人格、任务类型、发起体验评审等）。

    两种"没有身份"必须区别对待，这是本函数存在的全部要点：
      · 压根没带令牌 → 匿名。"不登录也能试用"这条产品线全靠它，不能动。
      · 带了令牌但它无效 → 401 session_expired，绝不悄悄降级成匿名。
        以前这里对所有 Unauthorized 一律 except 掉回落匿名，后果不是"少了个提示"：
        token 一过期，用户新发起的评审归属直接落到共享匿名桶（认领不回来的那种
        错主人）、报告被匿名门禁裁剪、/history 空白、/keys 显示没配 key——
        每一项单看都像"数据没了"，而后端从头到尾返回 200。
    """
    if bearer_token(authorization) is None:
        return Identity(user_id=settings.anonymous_user_id, is_anonymous=True)
    return await current_identity(request, authorization, db)


async def probe_identity(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Identity:
    """「我是谁」探测口（/auth/me 专用）：唯一允许令牌失效还返回 200 的地方。

    为什么要开这个例外：前端启动时得先问一句"我现在是谁"，才能决定是清掉
    过期 token 并提示重新登录、还是按匿名继续。如果这一问也 401，前端只能
    看到一个失败的请求，既拿不到"你现在是匿名"也拿不到"你的令牌过期了"，
    烂 token 会一直躺在 localStorage 里，每个后续请求继续 401。
    失败在这里不是被吞掉，而是被如实翻译成 session_expired=true 带回前端。
    """
    if bearer_token(authorization) is None:
        return Identity(user_id=settings.anonymous_user_id, is_anonymous=True)
    try:
        return await current_identity(request, authorization, db)
    except Unauthorized:
        return Identity(
            user_id=settings.anonymous_user_id, is_anonymous=True, session_expired=True
        )


def is_shared_anonymous(identity: Identity) -> bool:
    """当前身份是不是那个**所有人共用**的匿名桶。

    注意 is_anonymous 不足以判断：CDK 兑换出来的游客也走 optional_identity，
    但他们持 token、有独立 user_id、is_anonymous=False，是真实且互相隔离的身份。
    真正危险的只有 user_id == settings.anonymous_user_id 这一种。
    """
    return identity.is_anonymous and identity.user_id == settings.anonymous_user_id


def require_isolated_identity(identity: Identity) -> None:
    """个人数据接口的守卫：多租户形态下不接受共享匿名桶。

    为什么需要它，而 config._validate_startup 里那道检查不够：
    那道检查只在 AL_AUTH_ENABLED=false 时报错，措辞是「关闭认证时所有请求共用
    同一个 anonymous 身份——访客能看到彼此的评审、彼此的用量和彼此填的 API Key」。
    但同一句话对 **AL_AUTH_ENABLED=true 时的未登录访客**一字不差地成立：
    optional_identity 在没有有效 token 时同样回落到 anonymous_user_id，
    于是张三未登录跑的评审，李四打开网站就能列出来、连结论原文一起读到。
    实测（不带任何令牌直接请求后端）确实能拿到别人的评审列表与全部判断记录。

    两种形态都要保住，所以判定条件是 auth_enabled 而不是一刀切：
      · AL_AUTH_ENABLED=false —— 单机开源形态，这台机器就一个人用，
        anonymous 桶就是「我」，照常放行（否则自建用户全部用不了）。
      · AL_AUTH_ENABLED=true  —— 多租户形态，anonymous 是公共空间，
        任何「属于某个人」的读写都必须先有身份。

    只用于个人数据（自己的 key / 自己的评审列表 / 自己的判断台账）。
    发起评审这类「先体验后注册」的动作不挂它——匿名照样能跑，
    跑完用 /auth/me/claim-reviews 认领到账号下。
    """
    if settings.auth_enabled and is_shared_anonymous(identity):
        raise Unauthorized(
            "这个接口返回的是「属于你自己的」数据，未登录时无法区分谁是谁"
            "（未登录访客共用同一个匿名身份）。请先登录或注册。"
        )


def resolve_rate_limit(db: Session, scope: str, limit: Optional[int] = None) -> int:
    """本次限流用哪个上限。优先级：调用方显式 limit > scope 专属旋钮 > 通用每分钟上限。

    每一档都先查后台覆盖值再回落 env，所以面板上改完立刻生效、无需重启。
    """
    if limit is not None:
        return limit
    setting_key = _SCOPE_LIMIT_SETTINGS.get(scope, "ratelimit_per_minute")
    return admin_settings_service.get(db, setting_key, getattr(settings, setting_key))


def rate_limit(scope: str = "default", limit: int = None, window: float = 60.0):
    """限流依赖工厂。用法： dependencies=[Depends(rate_limit("review", None, 3600))]

    limit=None 时按 scope 解析默认上限（见 _SCOPE_LIMIT_SETTINGS）——
    所以 scope 字符串是有语义的，"review" 会读「评审接口限流（次/小时）」，
    其余 scope 读「通用接口限流（次/分钟）」。窗口仍由调用方指定，
    两者要对得上（review 的窗口就该是 3600）。
    ratelimit_enabled 与两个上限都支持后台面板实时覆盖，无需重启。
    """

    async def _dep(
        request: Request,
        identity: Identity = Depends(optional_identity),
        db: Session = Depends(get_db),
    ):
        if not admin_settings_service.get(db, "ratelimit_enabled", settings.ratelimit_enabled):
            return
        cap = resolve_rate_limit(db, scope, limit)
        key = f"{scope}:{_client_key(request, identity.user_id)}"
        if not get_limiter().allow(key, cap, window):
            raise RateLimited(
                f"「{scope}」操作过于频繁（限 {cap} 次 / {int(window)}s），请稍后再试。"
            )

    return _dep


def resolve_llm_key(
    identity: Identity = Depends(optional_identity), db: Session = Depends(get_db)
):
    """解析本次调用该用谁的 key —— 无可用 key 时抛 428 LLMKeyMissing。

    用 optional_identity 而非 current_identity：渐进式认证下匿名必须也能发评审
    （"体验机会"），登录只是让 key 归属和配额落到真实身份而不是共享的 anonymous 桶。
    """
    return key_service.resolve_key(db, identity.user_id)


def reset_admin_auth_failures(client_key: Optional[str] = None) -> None:
    """清空后台令牌失败计数。测试用；运维想解锁也可以调（重启进程同样有效）。"""
    with _admin_auth_lock:
        if client_key is None:
            _admin_auth_failures.clear()
        else:
            _admin_auth_failures.pop(client_key, None)


def _admin_auth_locked_for(client_key: str) -> float:
    """还要锁多少秒；0 表示没锁。只读，不消耗计数。"""
    with _admin_auth_lock:
        state = _admin_auth_failures.get(client_key)
        if state is None:
            return 0.0
        count, started = state
        remaining = ADMIN_AUTH_WINDOW_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            _admin_auth_failures.pop(client_key, None)
            return 0.0
        return remaining if count >= ADMIN_AUTH_MAX_FAILURES else 0.0


def _admin_auth_record_failure(client_key: str) -> None:
    with _admin_auth_lock:
        now = time.monotonic()
        state = _admin_auth_failures.get(client_key)
        if state is None or now - state[1] > ADMIN_AUTH_WINDOW_SECONDS:
            _admin_auth_failures[client_key] = [1, now]
        else:
            state[0] += 1


def _tokens_match(provided: str, expected: str) -> bool:
    """恒定时间比较。

    先 encode 成 bytes：hmac.compare_digest 对含非 ASCII 的 str 会抛 TypeError，
    直接传字符串意味着任何人发一个中文令牌就能把每个后台请求打成 500。
    """
    try:
        return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
    except (AttributeError, TypeError, UnicodeError):
        return False


async def require_admin(
    request: Request, x_admin_token: Optional[str] = Header(default=None)
) -> None:
    """后台管理接口守卫：未配置 AL_ADMIN_TOKEN 时整体 503，配置了则校验共享密钥。

    三层防护：
      1. 恒定时间比较（_tokens_match），不泄露 timing side-channel；
      2. 失败计数 + 锁定：/api/admin/* 是唯一没挂通用限流的路由前缀，
         而令牌是静态共享密钥、无有效期，不挡失败次数就等于允许离线枚举；
      3. 令牌强度下限在启动时校验（config.Settings._validate_admin_token）。
    成功一次即清零计数——管理员正常轮询不会把自己锁出去。
    """
    if not settings.admin_enabled:
        raise AdminDisabled()

    client_key = _client_key(request)
    locked_for = _admin_auth_locked_for(client_key)
    if locked_for > 0:
        raise RateLimited(
            f"管理员令牌校验失败次数过多，请 {int(locked_for) + 1} 秒后再试。"
        )

    if not x_admin_token or not _tokens_match(x_admin_token, settings.admin_token):
        _admin_auth_record_failure(client_key)
        logger.warning("后台令牌校验失败 | %s", client_key)
        raise Unauthorized("管理员令牌无效")

    reset_admin_auth_failures(client_key)
