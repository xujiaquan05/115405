# backend/tests/test_time_utils.py

from datetime import datetime, timezone

from app.core.time_utils import taiwan_now


def test_taiwan_now_is_utc_plus_8():
    utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    taiwan = taiwan_now()

    diff_hours = (taiwan - utc_naive).total_seconds() / 3600

    # 台灣沒有日光節約時間，所以永遠是 +8。
    assert 7.99 < diff_hours < 8.01


def test_taiwan_now_is_naive():
    # DB 裡的 published_at 是 naive datetime，
    # taiwan_now 也必須是 naive 才能互相比較。
    assert taiwan_now().tzinfo is None
