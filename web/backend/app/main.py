"""FastAPI 应用装配。

启动顺序（每一步都可在 app/config.py 里开关）：
    日志 → DB 建表/迁移 → 预热人格与评估器 → 中间件 → 路由 → 错误处理

路由分三层：
    api_router      原有业务路由（personas / task-types / reviews v1 / evaluations …）
    platform_router 平台链路（health / auth / keys / intent / uploads / usage /
                    v2 异步评审 / jobs / 判断复利闭环）
    admin_router    后台管理（运行时配置 / 平台级 key / 系统概览 / 任务与评审巡检），
                    未设置 AL_ADMIN_TOKEN 时整体 503，见 deps.require_admin
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import router as api_router
from app.api.admin import auth_router as admin_auth_router
from app.api.admin import router as admin_router
from app.api.platform import router as platform_router
from app.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import logger, request_context_middleware, setup_logging
from app.db import engine, init_db  # noqa: F401  (engine 供既有代码 import)
from app.websocket import manager as ws_manager
from app.websocket import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.debug)
    init_db()

    # 预热：人格库、评估器、伦理规则（失败不应拖垮启动，故逐个兜住）
    try:
        from app.services import PersonaService

        PersonaService.load_all_personas()
        PersonaService.load_agents_from_md()
        PersonaService.load_trae_personas()
        PersonaService.list_packs()
        PersonaService.load_presets()

        from app.services.evaluation_service import EvaluationService

        EvaluationService.load_evaluators()
        EvaluationService.load_rubrics()

        from app.services.ethics_service import EthicsService

        EthicsService._load_stereotype_patterns()
    except Exception as exc:
        logger.warning("预热失败（不影响启动）: %s", exc)

    ws_manager.set_loop(asyncio.get_running_loop())
    logger.info("AudienceLens API 就绪 | %s", settings.sanitized())
    try:
        yield
    finally:
        from app.services import job_service

        job_service.shutdown_backend()


app = FastAPI(title="AudienceLens Review API", version="0.3.0", lifespan=lifespan)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全响应头：防 MIME 嗅探、点击劫持等。"""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class GuestCookieMiddleware(BaseHTTPMiddleware):
    """把依赖里铸造 / 作废的游客身份写成 Set-Cookie（见 deps.resolve_guest_identity）。

    放在中间件而不是依赖里：依赖只能改 FastAPI 注入的临时 Response，
    路由自己返回 JSONResponse、或抛错走 error handler 时那些头会丢——
    而铸造已经落库了，cookie 丢了就等于这个访客下一个请求又被铸成另一个人。
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        token = getattr(request.state, "guest_cookie_token", None)
        if token:
            response.set_cookie(
                settings.guest_cookie_name,
                token,
                max_age=settings.guest_cookie_ttl_seconds,
                httponly=True,
                secure=settings.guest_cookie_secure,
                samesite="lax",
                path="/",
            )
        elif getattr(request.state, "clear_guest_cookie", False):
            response.delete_cookie(
                settings.guest_cookie_name,
                path="/",
                httponly=True,
                secure=settings.guest_cookie_secure,
                samesite="lax",
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GuestCookieMiddleware)
app.middleware("http")(request_context_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # X-Total-Count：GET /api/reviews 的总条数放在头里（见 api/__init__.py 的说明）。
    # 不在这里 expose，跨域部署下浏览器根本读不到这个头，历史页的"共 N 条"会静默
    # 退化成"这一页装满了就说明还有更多"——功能不报错，但数字永远显示不出来。
    expose_headers=["X-Request-Id", "X-Total-Count"],
)

register_error_handlers(app)

app.include_router(api_router)
app.include_router(platform_router, prefix="/api")  # /api/health 在 platform 里
app.include_router(admin_router, prefix="/api")
app.include_router(admin_auth_router, prefix="/api")
app.include_router(ws_router)
