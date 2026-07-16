"""结构化错误：所有链路共用一套错误契约。

前端只需认 {error: {code, message, detail}}，不必猜 HTTP body 形状。
新增错误时继承 AppError 并给一个稳定的 code（前端可据此做分支）。
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 500
    code = "internal_error"
    message = "服务器内部错误"

    def __init__(self, message: str = None, detail=None):
        self.message = message or self.__class__.message
        self.detail = detail
        super().__init__(self.message)

    def to_payload(self) -> dict:
        payload = {"error": {"code": self.code, "message": self.message}}
        if self.detail is not None:
            payload["error"]["detail"] = self.detail
        return payload


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    message = "资源不存在"


class BadRequest(AppError):
    status_code = 400
    code = "bad_request"
    message = "请求参数有误"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"
    message = "需要登录"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"
    message = "无权访问"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"
    message = "请求过于频繁，请稍后再试"


class QuotaExceeded(AppError):
    status_code = 402
    code = "quota_exceeded"
    message = "已超出配额"


class LLMKeyMissing(AppError):
    """BYOK 模式下用户没提供 key —— 前端应引导用户去设置页填写。"""

    status_code = 428  # Precondition Required
    code = "llm_key_missing"
    message = (
        "未配置 LLM API Key。AudienceLens 的评审必须使用真实模型——"
        "模拟数据没有评审价值。请在设置中填写你的 API Key。"
    )


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_error"
    message = "上游模型服务异常"


class AdminDisabled(AppError):
    """未设置 AL_ADMIN_TOKEN 时，后台管理接口整体不可用——安全默认值。"""

    status_code = 503
    code = "admin_disabled"
    message = "后台管理面板未启用。请在服务端设置 AL_ADMIN_TOKEN 环境变量后重启。"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    from app.config import settings

    payload = {"error": {"code": "internal_error", "message": "服务器内部错误"}}
    if settings.debug:
        payload["error"]["detail"] = f"{type(exc).__name__}: {exc}"
    return JSONResponse(status_code=500, content=payload)


def register_error_handlers(app) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
