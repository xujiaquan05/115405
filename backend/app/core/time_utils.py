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


def utc_now() -> datetime:
    """UTC 的現在時間（naive）。

    只給「要和 JWT 的 iat 比較」的欄位使用，例如 password_changed_at。
    JWT 的 iat 是 UTC 時戳，若改用 taiwan_now()（快 8 小時），
    會把剛簽發的 token 也判定成「密碼變更前簽發」而全部擋掉。
    """
    return datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)
