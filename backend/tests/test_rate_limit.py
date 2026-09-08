# backend/tests/test_rate_limit.py

"""IP 頻率限制。

計數改存資料庫（原本在 process 記憶體），所以測試要給一個真的 session。
限制器本身是 FastAPI dependency，測試直接呼叫時得自己把 session 傳進去。
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.rate_limit import RateLimiter, clear_rate_limits
from app.models.database_models import RateLimitHit


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def make_request(ip="1.2.3.4", forwarded=None):
    headers = {}

    if forwarded:
        headers["x-forwarded-for"] = forwarded

    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=ip))


class TestRateLimiter:
    def test_allows_up_to_limit(self, db):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        request = make_request()

        for _ in range(3):
            limiter(request, db)  # 不應該 raise

    def test_rejects_over_limit_with_429(self, db):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        request = make_request()

        for _ in range(3):
            limiter(request, db)

        with pytest.raises(HTTPException) as exc_info:
            limiter(request, db)

        assert exc_info.value.status_code == 429

    def test_different_ips_counted_separately(self, db):
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        for _ in range(2):
            limiter(make_request(ip="1.1.1.1"), db)

        # 另一個 IP 不該被前一個用掉的額度影響。
        limiter(make_request(ip="2.2.2.2"), db)

    def test_forwarded_for_takes_priority(self, db):
        """Render 會經過 proxy，真實 IP 在 X-Forwarded-For 的第一個元素；
        若只看 request.client.host，所有使用者會共用同一份額度。"""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        limiter(make_request(ip="10.0.0.1", forwarded="203.0.113.9, 10.0.0.1"), db)

        with pytest.raises(HTTPException):
            limiter(make_request(ip="10.0.0.2", forwarded="203.0.113.9, 10.0.0.2"), db)

    def test_window_expiry_allows_again(self, db):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        request = make_request()

        limiter(request, db)

        # 把視窗起點往回推，模擬時間經過。
        row = db.query(RateLimitHit).one()
        row.window_start = row.window_start - timedelta(seconds=61)
        db.commit()

        limiter(request, db)  # 視窗過了應該重新計數

        assert db.query(RateLimitHit).one().count == 1

    def test_scopes_do_not_share_quota(self, db):
        """登入與問答各自計數，問答用完不該把登入也擋住。"""
        login = RateLimiter(max_requests=1, window_seconds=60, scope="login")
        qa = RateLimiter(max_requests=1, window_seconds=60, scope="qa")
        request = make_request()

        login(request, db)
        qa(request, db)  # 不同 scope，不受影響

        with pytest.raises(HTTPException):
            login(request, db)


class TestClearRateLimits:
    def test_clears_all_counters(self, db):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter(make_request(), db)

        clear_rate_limits(db)

        limiter(make_request(), db)  # 清掉後可以重新開始
