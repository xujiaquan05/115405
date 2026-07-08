# backend/app/core/rate_limit.py

import threading
import time
from collections import deque

from fastapi import HTTPException, Request


class RateLimiter:
    """
    說明：
    Sliding window 型的 rate limiter，依 IP 計算請求次數。

    因為狀態存在 RAM，只有單一 process（如目前 Render 的部署方式）
    才正確；若之後要 scale 多個 worker，必須改用 Redis，
    和 CACHE_STORE、WebSocket manager 的限制相同。

    當作 FastAPI dependency 使用：
        limiter = RateLimiter(max_requests=10, window_seconds=60)

        @router.post("/ask", dependencies=[Depends(limiter)])
    """

    # 追蹤的 IP 數量超過此上限時，清掉太久沒動作的 IP，
    # 避免 public endpoint 的 dict 無限膨脹。
    MAX_TRACKED_CLIENTS = 1024

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _client_key(self, request: Request) -> str:
        # 在 Render 上請求會經過 proxy，
        # 真實 IP 在 X-Forwarded-For 的第一個元素。
        forwarded = request.headers.get("x-forwarded-for", "")

        if forwarded:
            return forwarded.split(",")[0].strip()

        return request.client.host if request.client else "unknown"

    def _cleanup_stale_clients(self, now: float):
        if len(self._hits) <= self.MAX_TRACKED_CLIENTS:
            return

        stale_keys = [
            key
            for key, hits in self._hits.items()
            if not hits or now - hits[-1] > self.window_seconds
        ]

        for key in stale_keys:
            del self._hits[key]

    def __call__(self, request: Request):
        key = self._client_key(request)
        now = time.monotonic()

        with self._lock:
            self._cleanup_stale_clients(now)

            hits = self._hits.setdefault(key, deque())

            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()

            if len(hits) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail="請求太頻繁，請稍後再試。",
                )

            hits.append(now)
