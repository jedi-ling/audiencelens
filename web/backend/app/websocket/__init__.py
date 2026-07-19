import asyncio
import json
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings

router = APIRouter()

# 安全措施：WebSocket origin 白名单，防止跨站 WebSocket 劫持。
# 生产部署时用 AL_CORS_ORIGINS 配置真实域名（与 HTTP CORS 同源）。
ALLOWED_WS_ORIGINS = set(settings.cors_origins) | {"http://127.0.0.1:5173"}


class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, List[WebSocket]] = defaultdict(list)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, review_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active[review_id].append(websocket)

    def disconnect(self, review_id: str, websocket: WebSocket):
        if review_id in self.active:
            self.active[review_id] = [ws for ws in self.active[review_id] if ws is not websocket]
            if not self.active[review_id]:
                del self.active[review_id]

    async def broadcast(self, review_id: str, data: Dict[str, Any]):
        if review_id not in self.active:
            return
        message = json.dumps(data, ensure_ascii=False)
        disconnected = []
        for ws in self.active[review_id]:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(review_id, ws)

    def broadcast_sync(self, review_id: str, data: Dict[str, Any]):
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                return
        if self._loop is not None and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.broadcast(review_id, data), self._loop)

    # 后台 worker 线程用这个入口推进度（语义比 broadcast_sync 更明确）
    def publish_threadsafe(self, review_id: str, data: Dict[str, Any]):
        self.broadcast_sync(review_id, data)


manager = ConnectionManager()

# WS 事件契约（前端据此分支；新增事件请同步更新 docs/ARCHITECTURE.md）
WS_EVENTS = (
    "review.started",
    "review.progress",
    "review.persona_completed",
    "review.completed",
    "review.failed",
)


def _resolve_ws_user(websocket: WebSocket) -> str:
    """从 ?token= 解析身份；无 token 或 token 无效一律按匿名处理。

    浏览器 WebSocket API 不能带自定义 header，所以 token 走查询参数。
    与 HTTP 侧 optional_identity 同一哲学：不 401，静默回落匿名。
    """
    token = websocket.query_params.get("token") or ""
    if not token:
        return settings.anonymous_user_id
    try:
        from app.core.security import decode_token

        payload = decode_token(token, settings.jwt_secret)
        return str(payload.get("sub") or settings.anonymous_user_id)
    except Exception:
        return settings.anonymous_user_id


@router.websocket("/ws/review/{review_id}")
async def review_websocket(websocket: WebSocket, review_id: str):
    # 安全措施：验证 WebSocket 连接的 origin，防止跨站劫持攻击
    origin = websocket.headers.get("origin", "")
    if origin and origin not in ALLOWED_WS_ORIGINS:
        await websocket.close(code=4001, reason="Origin not allowed")
        return

    # 归属校验：登录用户的评审只有本人能订阅——
    # 不做这一步的话，任何人拿到 review_id 就能旁听别人的报告内容
    from app.db import SessionLocal
    from app.models import Review

    db = SessionLocal()
    try:
        review = db.get(Review, review_id)
    finally:
        db.close()
    if review is None:
        await websocket.close(code=4404, reason="Review not found")
        return
    owner = review.user_id or settings.anonymous_user_id
    if owner != settings.anonymous_user_id:
        if _resolve_ws_user(websocket) != owner:
            await websocket.close(code=4403, reason="Not your review")
            return

    if manager._loop is None:
        manager.set_loop(asyncio.get_running_loop())
    await manager.connect(review_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(review_id, websocket)
