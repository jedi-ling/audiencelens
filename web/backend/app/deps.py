"""依赖注入：所有链路的入口守卫都在这里，路由只管业务。

一条评审请求要过的关卡（顺序即依赖顺序）：
    rate_limit → current_identity → resolve_llm_key → check_quota
每一关都可通过 app/config.py 的开关独立启停。
"""

import hmac
from typing import Optional

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AdminDisabled, RateLimited, Unauthorized
from app.core.ratelimit import get_limiter
from app.core.security import decode_token
from app.db import get_db
from app.models import User
from app.services import admin_settings_service, key_service


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


def rate_limit(scope: str = "default", limit: int = None, window: float = 60.0):
    """限流依赖工厂。用法： dependencies=[Depends(rate_limit("review", 20, 3600))]

    ratelimit_enabled / 通用每分钟上限支持后台面板实时覆盖（无需重启）；
    调用方显式传入的 limit（如评审接口的每小时上限）优先级最高，不被覆盖值影响。
    """

    async def _dep(
        request: Request,
        identity: Identity = Depends(optional_identity),
        db: Session = Depends(get_db),
    ):
        if not admin_settings_service.get(db, "ratelimit_enabled", settings.ratelimit_enabled):
            return
        cap = limit if limit is not None else admin_settings_service.get(
            db, "ratelimit_per_minute", settings.ratelimit_per_minute
        )
        key = f"{scope}:{_client_key(request, identity.user_id)}"
        if not get_limiter().allow(key, cap, window):
            raise RateLimited(
                f"「{scope}」操作过于频繁（限 {cap} 次 / {int(window)}s），请稍后再试。"
            )

    return _dep


def resolve_llm_key(
    identity: Identity = Depends(current_identity), db: Session = Depends(get_db)
):
    """解析本次调用该用谁的 key —— 无可用 key 时抛 428 LLMKeyMissing。"""
    return key_service.resolve_key(db, identity.user_id)


async def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    """后台管理接口守卫：未配置 AL_ADMIN_TOKEN 时整体 503，配置了则校验共享密钥。

    用 hmac.compare_digest 做恒定时间比较，避免逐字节比较泄露 timing side-channel
    （与 core/security.py 里 JWT 签名校验、密钥密文校验同一套谨慎标准）。
    """
    if not settings.admin_enabled:
        raise AdminDisabled()
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise Unauthorized("管理员令牌无效")
