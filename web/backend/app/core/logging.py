"""结构化日志 + 请求 ID。

每条日志带 request_id，排查线上问题时可把一次请求的全链路串起来。
换成 JSON 日志/接入 Sentry 时，只需改 _emit 与 RequestContextMiddleware。
"""

import contextvars
import logging
import sys
import time
import uuid

request_id_var: contextvars.ContextVar = contextvars.ContextVar("request_id", default="-")

logger = logging.getLogger("audiencelens")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging(debug: bool = False) -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    handler.addFilter(_RequestIdFilter())
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False


async def request_context_middleware(request, call_next):
    """给每个请求打 ID、记耗时；响应头回传 X-Request-Id 便于用户报障。"""
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    token = request_id_var.set(rid)
    started = time.time()
    try:
        response = await call_next(request)
    finally:
        elapsed = (time.time() - started) * 1000
        if not request.url.path.startswith(("/health", "/docs", "/openapi")):
            logger.info("%s %s %.0fms", request.method, request.url.path, elapsed)
        request_id_var.reset(token)
    response.headers["X-Request-Id"] = rid
    return response
