# backend/tests/test_time_utils.py

from datetime import datetime, timezone

from app.core.time_utils import taiwan_now


def test_taiwan_now_is_utc_plus_8():
    utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    taiwan = taiwan_now()

    diff_hours = (taiwan - utc_naive).total_seconds() / 3600

    # Đài Loan không có daylight saving nên luôn đúng +8.
    assert 7.99 < diff_hours < 8.01


def test_taiwan_now_is_naive():
    # published_at trong DB là naive datetime,
    # nên taiwan_now cũng phải naive để so sánh được.
    assert taiwan_now().tzinfo is None
