# backend/app/services/cache_service.py

from datetime import datetime, timedelta, timezone


def _now():
    # datetime.utcnow() 已被 Python 標記為 deprecated，
    # 改用帶時區的 UTC 時間；cache 內部只互相比較，所以安全。
    return datetime.now(timezone.utc)


# 說明：
# 這是存在 RAM 的暫存 cache。
# Key 是查詢條件，Value 是 dashboard 資料 + 到期時間。
#
# 限制：cache 存在單一 process 的 RAM 中，只有跑 1 個 worker
# （如目前的部署方式）才正確；若要 scale 多 worker 必須改用 Redis。
CACHE_STORE = {}

# 說明：
# 每一組 keyword + days + boards 都是一個新 entry，
# 而過期 entry 只有在同一個 key 再次被讀取時才會刪除，
# 所以必須設上限，避免 cache 隨時間無限膨脹。
MAX_CACHE_ITEMS = 256


def _evict_if_full():
    if len(CACHE_STORE) < MAX_CACHE_ITEMS:
        return

    now = _now()
    expired_keys = [
        key
        for key, item in CACHE_STORE.items()
        if item["expires_at"] < now
    ]

    for key in expired_keys:
        del CACHE_STORE[key]

    # 如果清完過期 entry 還是滿的，
    # 就刪掉最接近到期的 entry（近似最舊的 entry）。
    while len(CACHE_STORE) >= MAX_CACHE_ITEMS:
        oldest_key = min(CACHE_STORE, key=lambda key: CACHE_STORE[key]["expires_at"])
        del CACHE_STORE[oldest_key]


def get_cache(key: str):
    """
    依 key 取得 cache 資料。

    情況：
    - key 不存在 => 回傳 None
    - cache 已過期 => 刪除該 cache 後回傳 None
    - cache 未過期 => 回傳資料
    """

    cache_item = CACHE_STORE.get(key)

    if cache_item is None:
        return None

    expires_at = cache_item["expires_at"]

    if _now() > expires_at:
        del CACHE_STORE[key]
        return None

    return cache_item["data"]


def set_cache(key: str, data, minutes: int = 30):
    """
    寫入 cache。

    minutes = 30 表示：
    30 分鐘內如果 user 用相同條件查詢，
    backend 會直接回傳 cache，不再查 database。
    """

    _evict_if_full()

    CACHE_STORE[key] = {
        "data": data,
        "expires_at": _now() + timedelta(minutes=minutes),
    }
