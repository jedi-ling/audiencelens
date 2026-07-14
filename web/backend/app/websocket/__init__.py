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


@router.websocket("/ws/review/{review_id}")
async def review_websocket(websocket: WebSocket, review_id: str):
    # 安全措施：验证 WebSocket 连接的 origin，防止跨站劫持攻击
    origin = websocket.headers.get("origin", "")
    if origin and origin not in ALLOWED_WS_ORIGINS:
        await websocket.close(code=4001, reason="Origin not allowed")
        return
    if manager._loop is None:
        manager.set_loop(asyncio.get_running_loop())
    await manager.connect(review_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(review_id, websocket)
