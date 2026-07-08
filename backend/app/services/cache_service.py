# backend/app/services/cache_service.py

from datetime import datetime, timedelta


# Note:
# Đây là cache tạm lưu trong RAM.
# Key là điều kiện query.
# Value là dữ liệu dashboard + thời gian hết hạn.
#
# Giới hạn: cache nằm trong RAM của 1 process, nên chỉ đúng khi chạy
# 1 worker (như deploy hiện tại). Nếu scale nhiều worker phải chuyển
# sang Redis.
CACHE_STORE = {}

# Note:
# Mỗi tổ hợp keyword + days + boards là một entry mới, và entry hết hạn
# chỉ bị xóa khi có người đọc lại đúng key đó — nên phải chặn trần
# số entry để cache không phình vô hạn theo thời gian.
MAX_CACHE_ITEMS = 256


def _evict_if_full():
    if len(CACHE_STORE) < MAX_CACHE_ITEMS:
        return

    now = datetime.utcnow()
    expired_keys = [
        key
        for key, item in CACHE_STORE.items()
        if item["expires_at"] < now
    ]

    for key in expired_keys:
        del CACHE_STORE[key]

    # Nếu dọn entry hết hạn rồi mà vẫn đầy,
    # xóa entry gần hết hạn nhất (xấp xỉ entry cũ nhất).
    while len(CACHE_STORE) >= MAX_CACHE_ITEMS:
        oldest_key = min(CACHE_STORE, key=lambda key: CACHE_STORE[key]["expires_at"])
        del CACHE_STORE[oldest_key]


def get_cache(key: str):
    """
    Note:
    Lấy dữ liệu cache theo key.

    Nếu:
    - key không tồn tại => return None
    - cache hết hạn => xóa cache rồi return None
    - cache còn hạn => return data
    """

    cache_item = CACHE_STORE.get(key)

    if cache_item is None:
        return None

    expires_at = cache_item["expires_at"]

    if datetime.utcnow() > expires_at:
        del CACHE_STORE[key]
        return None

    return cache_item["data"]


def set_cache(key: str, data, minutes: int = 30):
    """
    Note:
    Lưu dữ liệu vào cache.

    minutes = 30 nghĩa là:
    trong 30 phút nếu user query cùng điều kiện,
    backend sẽ trả cache thay vì query database lại.
    """

    _evict_if_full()

    CACHE_STORE[key] = {
        "data": data,
        "expires_at": datetime.utcnow() + timedelta(minutes=minutes),
    }