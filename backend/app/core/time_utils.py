# backend/app/core/time_utils.py

from datetime import datetime
from zoneinfo import ZoneInfo

# Note:
# published_at của bài viết được parse trực tiếp từ trang PTT,
# tức là giờ Đài Loan (UTC+8) và lưu dạng naive datetime.
#
# Vì vậy mọi phép so sánh "hiện tại" với published_at phải dùng
# giờ Đài Loan. Nếu dùng datetime.utcnow() (chậm hơn 8 tiếng),
# điều kiện published_at <= now sẽ loại nhầm toàn bộ bài viết
# đăng trong 8 giờ gần nhất.
TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def taiwan_now() -> datetime:
    return datetime.now(TAIPEI_TZ).replace(tzinfo=None)
