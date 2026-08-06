# backend/app/services/settings_service.py

import os

from sqlalchemy.orm import Session

from app.core.time_utils import taiwan_now
from app.models.database_models import Setting


def _env_bool(name: str, default: str) -> str:
    return os.getenv(name, default)


# 說明：
# 所有可調參數的定義：預設值（字串）＋型別。
# 預設值沿用目前的環境變數，確保還沒有人改設定前行為不變。
# type 用於「輸出時解析」與「輸入時驗證」。
SETTING_DEFS = {
    "alert_warning_negative": (os.getenv("ALERT_WARNING_NEGATIVE", "25"), float),
    "alert_critical_negative": (os.getenv("ALERT_CRITICAL_NEGATIVE", "40"), float),
    "alert_min_articles": (os.getenv("ALERT_MIN_ARTICLES", "5"), int),
    "auto_crawl_enabled": (_env_bool("AUTO_CRAWL_ENABLED", "true"), bool),
    "auto_crawl_hour": (os.getenv("AUTO_CRAWL_HOUR", "3"), int),
    "auto_crawl_pages": (os.getenv("AUTO_CRAWL_PAGES", "2"), int),
}


def _parse(raw: str, kind) -> object:
    if kind is bool:
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if kind is int:
        return int(float(raw))
    if kind is float:
        return float(raw)
    return raw


def get_setting(db: Session, key: str):
    """取得單一設定值（已依型別解析）；沒設定過就回傳預設值。"""
    default_raw, kind = SETTING_DEFS[key]
    row = db.query(Setting).filter(Setting.key == key).first()
    raw = row.value if row is not None and row.value is not None else default_raw

    try:
        return _parse(raw, kind)
    except (ValueError, TypeError):
        return _parse(default_raw, kind)


def get_all_settings(db: Session) -> dict:
    """回傳所有設定（已解析），供後台設定頁顯示。"""
    return {key: get_setting(db, key) for key in SETTING_DEFS}


def update_settings(db: Session, values: dict) -> dict:
    """
    批次更新設定。只接受 SETTING_DEFS 內的 key，並依型別驗證後存為字串。
    回傳更新後的完整設定。
    """
    now = taiwan_now()

    for key, value in values.items():
        if key not in SETTING_DEFS:
            continue

        _default_raw, kind = SETTING_DEFS[key]
        # 先驗證能否轉成正確型別（不行就跳過該筆）。
        try:
            parsed = _parse(value, kind)
        except (ValueError, TypeError):
            continue

        stored = "true" if (kind is bool and parsed) else "false" if kind is bool else str(parsed)

        row = db.query(Setting).filter(Setting.key == key).first()
        if row is None:
            db.add(Setting(key=key, value=stored, updated_at=now))
        else:
            row.value = stored
            row.updated_at = now

    db.commit()
    return get_all_settings(db)
