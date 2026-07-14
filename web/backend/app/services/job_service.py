"""异步任务队列（埋线：进程内线程池；AL_QUEUE_BACKEND=external 时换外部队列）。

为什么需要队列：一次评审要调数十次 LLM，几十秒到几分钟。
HTTP 请求里同步跑会超时、会阻塞其他用户。所以：
    POST /api/reviews  → 落库 + 入队 + 立刻返回 review_id（202）
    前端用 WebSocket 订阅进度，或轮询 GET /api/reviews/{id}

换 Celery/RQ：实现 JobBackend 协议（submit/cancel），在 get_backend() 返回它。
Job 表已落库，前端契约（review_id + WS 事件）完全不变。
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from app.config import settings
from app.core.logging import logger
from app.db import session_scope
from app.models import Job


class JobBackend:
    """任务后端协议。外部队列只需实现这两个方法。"""

    def submit(self, job_id: str, fn: Callable, *args, **kwargs) -> None:
        raise NotImplementedError

    def cancel(self, job_id: str) -> bool:
        raise NotImplementedError


class InProcessBackend(JobBackend):
    """线程池后端：单机部署足够。多副本部署请换外部队列。"""

    def __init__(self, workers: int):
        self._pool = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="al-job")
        self._futures: Dict[str, object] = {}
        self._cancelled: set = set()
        self._lock = threading.Lock()

    def submit(self, job_id: str, fn: Callable, *args, **kwargs) -> None:
        def _wrapped():
            if job_id in self._cancelled:
                _finish_job(job_id, "cancelled")
                return
            _start_job(job_id)
            try:
                fn(*args, **kwargs)
                _finish_job(job_id, "done", progress=100)
            except Exception as exc:  # 任务内异常不能吞：落库 + 打日志
                logger.exception("job %s failed: %s", job_id, exc)
                _finish_job(job_id, "failed", error=str(exc))
            finally:
                with self._lock:
                    self._futures.pop(job_id, None)

        with self._lock:
            self._futures[job_id] = self._pool.submit(_wrapped)

    def cancel(self, job_id: str) -> bool:
        """只能取消尚未开始的任务；已在跑的任务由业务侧自行检查取消标志。"""
        with self._lock:
            self._cancelled.add(job_id)
            fut = self._futures.get(job_id)
        if fut is not None and hasattr(fut, "cancel") and fut.cancel():
            _finish_job(job_id, "cancelled")
            return True
        return False

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancelled

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False)


_backend: Optional[JobBackend] = None


def get_backend() -> JobBackend:
    global _backend
    if _backend is None:
        if settings.queue_backend == "external":
            raise RuntimeError(
                "AL_QUEUE_BACKEND=external 但未接入外部队列。"
                "请实现 JobBackend 并在 get_backend() 中返回；见 docs/MAINTENANCE.md"
            )
        _backend = InProcessBackend(settings.queue_workers)
    return _backend


def shutdown_backend() -> None:
    global _backend
    if isinstance(_backend, InProcessBackend):
        _backend.shutdown()
    _backend = None


# ---------------- Job 表读写（外部队列也应复用，保证前端契约一致）----------------

def create_job(kind: str, ref_id: str = None, user_id: str = "anonymous", payload: dict = None) -> str:
    db = session_scope()
    try:
        job = Job(kind=kind, ref_id=ref_id, user_id=user_id, payload=payload or {}, status="queued")
        db.add(job)
        db.commit()
        db.refresh(job)
        return job.id
    finally:
        db.close()


def _start_job(job_id: str) -> None:
    db = session_scope()
    try:
        job = db.get(Job, job_id)
        if job:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def _finish_job(job_id: str, status: str, progress: int = None, error: str = None) -> None:
    db = session_scope()
    try:
        job = db.get(Job, job_id)
        if job:
            job.status = status
            job.finished_at = datetime.now(timezone.utc)
            if progress is not None:
                job.progress = progress
            if error:
                job.error_message = error[:2000]
            db.commit()
    finally:
        db.close()


def update_progress(job_id: str, progress: int) -> None:
    db = session_scope()
    try:
        job = db.get(Job, job_id)
        if job:
            job.progress = max(0, min(100, int(progress)))
            db.commit()
    finally:
        db.close()


def get_job(job_id: str) -> Optional[dict]:
    db = session_scope()
    try:
        job = db.get(Job, job_id)
        if not job:
            return None
        return {
            "id": job.id,
            "kind": job.kind,
            "ref_id": job.ref_id,
            "status": job.status,
            "progress": job.progress,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }
    finally:
        db.close()
