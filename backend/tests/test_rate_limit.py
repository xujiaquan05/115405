# backend/tests/test_rate_limit.py

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.rate_limit import RateLimiter


def make_request(ip="1.2.3.4", forwarded=None):
    headers = {}

    if forwarded:
        headers["x-forwarded-for"] = forwarded

    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=ip))


class TestRateLimiter:
    def test_allows_up_to_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        request = make_request()

        for _ in range(3):
            limiter(request)  # 不應該 raise

    def test_rejects_over_limit_with_429(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        request = make_request()

        for _ in range(3):
            limiter(request)

        with pytest.raises(HTTPException) as exc_info:
            limiter(request)

        assert exc_info.value.status_code == 429

    def test_different_ips_counted_separately(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        limiter(make_request(ip="1.1.1.1"))
        limiter(make_request(ip="2.2.2.2"))  # 不同 IP，不會被擋

    def test_forwarded_for_takes_priority(self):
        # 在 Render 上所有 request 都來自 proxy IP，
        # 必須依 X-Forwarded-For 計數，而不是 proxy 的 IP。
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        limiter(make_request(ip="10.0.0.1", forwarded="9.9.9.9, 10.0.0.1"))

        with pytest.raises(HTTPException):
            limiter(make_request(ip="10.0.0.2", forwarded="9.9.9.9"))

    def test_window_expiry_allows_again(self, monkeypatch):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        request = make_request()

        fake_time = [1000.0]
        monkeypatch.setattr(
            "app.core.rate_limit.time.monotonic",
            lambda: fake_time[0],
        )

        limiter(request)

        with pytest.raises(HTTPException):
            limiter(request)

        fake_time[0] += 61  # window 已過

        limiter(request)  # 重新允許，不會 raise
