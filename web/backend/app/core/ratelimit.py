"""限流（埋线：进程内令牌桶；多实例部署时换 Redis 后端）。

换 Redis：实现 RateLimiterBackend 协议并在 get_limiter() 里返回它即可，
调用方（deps.rate_limit）无需改动。
"""

import threading
import time
from collections import defaultdict


class InMemoryTokenBucket:
    """按 key 限流的令牌桶。单进程有效；多副本部署请换 Redis。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._buckets = defaultdict(lambda: None)  # key -> (tokens, last_refill_ts)

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        """window_seconds 内最多 limit 次。"""
        if limit <= 0:
            return True
        rate = limit / window_seconds
        now = time.monotonic()
        with self._lock:
            state = self._buckets[key]
            if state is None:
                self._buckets[key] = (limit - 1, now)
                return True
            tokens, last = state
            tokens = min(limit, tokens + (now - last) * rate)
            if tokens < 1:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1, now)
            return True

    def reset(self, key: str = None) -> None:
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)


_limiter = InMemoryTokenBucket()


def get_limiter() -> InMemoryTokenBucket:
    return _limiter
