# backend/app/services/lock_service.py

"""跨行程的互斥鎖（以資料庫為共享狀態）。

為什麼不用 threading.Lock？
threading.Lock 只在同一個 process 內有效。部署若開多個 worker，
每個 worker 各有一份鎖，等於沒有鎖。

為什麼不用 Redis？
Redis 是這類需求的標準答案，但會多一個要維運的服務。
本專案已經有 PostgreSQL，用一張表就能達到同樣效果，不必新增基礎設施。
"""

import logging
import os
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time_utils import taiwan_now
from app.models.database_models import SystemLock

logger = logging.getLogger(__name__)

CRAWL_LOCK = "crawler"

# 爬取可能跑很久（Dcard 逐篇進內頁時尤其慢），
# 設得太短會讓第二個請求在前一批還在跑時搶到鎖。
DEFAULT_TTL_MINUTES = 60


def _owner() -> str:
    return f"pid-{os.getpid()}"


def try_acquire(db: Session, name: str, ttl_minutes: int = DEFAULT_TTL_MINUTES) -> bool:
    """嘗試取得鎖，成功回傳 True。

    以主鍵的唯一性達成互斥：同名的列只會有一筆插入成功，
    其餘的會拿到 IntegrityError。這個行為在 PostgreSQL 與 SQLite 一致，
    因此測試不需要另外處理。
    """
    now = taiwan_now()
    expires_at = now + timedelta(minutes=ttl_minutes)

    try:
        db.add(SystemLock(name=name, acquired_at=now, expires_at=expires_at, owner=_owner()))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        # rollback 之後那筆失敗的物件仍留在 identity map，
        # 接著查詢同一把鎖時 SQLAlchemy 會發出衝突警告。清掉即可。
        db.expunge_all()

    # 已經有人持有：只有在鎖過期時才接手，
    # 避免持鎖的 worker 被強制關閉後永遠卡住。
    existing = db.query(SystemLock).filter(SystemLock.name == name).first()

    if existing is None:
        return False

    if existing.expires_at > now:
        return False

    logger.warning(
        "Taking over expired lock %s held by %s since %s",
        name, existing.owner, existing.acquired_at,
    )
    existing.acquired_at = now
    existing.expires_at = expires_at
    existing.owner = _owner()
    db.commit()
    return True


def release(db: Session, name: str) -> None:
    """釋放鎖。已經不存在時視為成功，重複呼叫不會出錯。"""
    db.query(SystemLock).filter(SystemLock.name == name).delete()
    db.commit()


def is_held(db: Session, name: str) -> bool:
    lock = db.query(SystemLock).filter(SystemLock.name == name).first()
    return lock is not None and lock.expires_at > taiwan_now()
