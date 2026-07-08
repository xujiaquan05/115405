# backend/app/core/time_utils.py

from datetime import datetime
from zoneinfo import ZoneInfo

# 說明：
# 文章的 published_at 是直接從 PTT 頁面解析出來的，
# 也就是台灣時間（UTC+8），並以 naive datetime 儲存。
#
# 因此所有和 published_at 比較的「現在時間」都必須用台灣時間。
# 如果用 datetime.utcnow()（慢 8 小時），
# published_at <= now 的條件會把最近 8 小時內發表的文章全部誤篩掉。
TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def taiwan_now() -> datetime:
    return datetime.now(TAIPEI_TZ).replace(tzinfo=None)
