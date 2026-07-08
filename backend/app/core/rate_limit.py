# backend/app/core/rate_limit.py

import threading
import time
from collections import deque

from fastapi import HTTPException, Request


class RateLimiter:
    """
    Note:
    Rate limiter kiểu sliding window, đếm request theo IP.

    Lưu trong RAM nên chỉ đúng khi chạy 1 process (như deploy hiện tại
    trên Render); nếu sau này scale nhiều worker thì phải chuyển
    sang Redis, giống như CACHE_STORE và WebSocket manager.

    Dùng làm FastAPI dependency:
        limiter = RateLimiter(max_requests=10, window_seconds=60)

        @router.post("/ask", dependencies=[Depends(limiter)])
    """

    # Khi số IP theo dõi vượt ngưỡng này thì dọn các IP đã im lặng lâu,
    # tránh dict phình vô hạn trên endpoint public.
    MAX_TRACKED_CLIENTS = 1024

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _client_key(self, request: Request) -> str:
        # Trên Render, request đi qua proxy nên IP thật nằm ở
        # X-Forwarded-For (phần tử đầu tiên).
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
