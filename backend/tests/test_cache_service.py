# backend/tests/test_cache_service.py

from datetime import datetime, timedelta, timezone

import pytest

from app.services import cache_service


def _expired_time():
    # cache_service 內部使用 timezone-aware UTC 時間，
    # 測試也必須用 aware datetime 才能比較。
    return datetime.now(timezone.utc) - timedelta(minutes=1)


@pytest.fixture(autouse=True)
def clean_cache():
    cache_service.CACHE_STORE.clear()
    yield
    cache_service.CACHE_STORE.clear()


class TestCacheBasics:
    def test_set_and_get(self):
        cache_service.set_cache("key1", {"value": 1})

        assert cache_service.get_cache("key1") == {"value": 1}

    def test_missing_key(self):
        assert cache_service.get_cache("missing") is None

    def test_expired_entry_removed(self):
        cache_service.set_cache("key1", "data")
        cache_service.CACHE_STORE["key1"]["expires_at"] = _expired_time()

        assert cache_service.get_cache("key1") is None
        assert "key1" not in cache_service.CACHE_STORE


class TestCacheEviction:
    def test_cache_size_stays_bounded(self, monkeypatch):
        monkeypatch.setattr(cache_service, "MAX_CACHE_ITEMS", 5)

        for index in range(20):
            cache_service.set_cache(f"key{index}", index)

        assert len(cache_service.CACHE_STORE) <= 5

    def test_expired_entries_evicted_first(self, monkeypatch):
        monkeypatch.setattr(cache_service, "MAX_CACHE_ITEMS", 3)

        # 把 cache 填到上限（3 個 entry），其中 1 個已過期。
        cache_service.set_cache("fresh1", 1)
        cache_service.set_cache("stale", 2)
        cache_service.set_cache("fresh2", 3)
        cache_service.CACHE_STORE["stale"]["expires_at"] = _expired_time()

        # cache 已滿時再寫入 => 先清掉過期 entry，
        # 未過期的 entry 保持不動。
        cache_service.set_cache("fresh3", 4)

        assert "stale" not in cache_service.CACHE_STORE
        assert cache_service.get_cache("fresh1") == 1
        assert cache_service.get_cache("fresh2") == 3
        assert cache_service.get_cache("fresh3") == 4
