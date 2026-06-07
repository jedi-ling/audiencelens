import asyncio
import json
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# 安全措施：WebSocket 允许的 origin 白名单，防止跨站 WebSocket 劫持
ALLOWED_WS_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://localhost:5175",
}


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


manager = ConnectionManager()


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
