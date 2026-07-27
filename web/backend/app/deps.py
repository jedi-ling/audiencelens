"""依赖注入：所有链路的入口守卫都在这里，路由只管业务。

一条评审请求要过的关卡（顺序即依赖顺序）：
    rate_limit → current_identity → resolve_llm_key → check_quota
每一关都可通过 app/config.py 的开关独立启停。
"""

import hmac
import threading
import time
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


class Identity:
    """统一身份对象：匿名与登录用户走同一套下游逻辑。"""

    def __init__(self, user_id: str, email: Optional[str] = None, plan: str = "free",
                 is_anonymous: bool = True):
        self.user_id = user_id
        self.email = email
        self.plan = plan
        self.is_anonymous = is_anonymous

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "plan": self.plan,
            "is_anonymous": self.is_anonymous,
        }


def _client_key(request: Request, identity_id: str = None) -> str:
    if identity_id and identity_id != settings.anonymous_user_id:
        return f"user:{identity_id}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


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

    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized()

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token, settings.jwt_secret)
    except ValueError as exc:
        raise Unauthorized(str(exc))

    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise Unauthorized("用户不存在或已停用")

    return Identity(
        user_id=user.id, email=user.email, plan=user.plan, is_anonymous=False
    )


async def optional_identity(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Identity:
    """不强制登录的只读接口用（列人格、任务类型等）。"""
    try:
        return await current_identity(request, authorization, db)
    except Unauthorized:
        return Identity(user_id=settings.anonymous_user_id, is_anonymous=True)


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
