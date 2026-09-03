# backend/app/core/startup.py

import logging
import os
from urllib.parse import quote

from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.models import database_models  # noqa: F401
from app.models.database_models import Plan, User
from app.services.article_service import get_or_create_board, get_or_create_platform
from app.services.auth_service import DEFAULT_ADMIN_PASSWORD, hash_password
from app.services.dashboard_service import (
    DCARD_BOARDS,
    MOBILE01_BOARDS,
    TARGET_BOARDS,
    THREADS_BOARDS,
)


logger = logging.getLogger(__name__)


def _apply_schema_migrations():
    # 說明：
    # create_all 只會建立新資料表，不會在既有資料表上新增欄位。
    # 專案尚未使用 Alembic，所以之後新增的欄位必須在這裡
    # 手動 ALTER TABLE（加 IF NOT EXISTS 讓重複執行也安全）。
    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS sentiment VARCHAR(20)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_articles_sentiment ON articles (sentiment)"
        ))
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP"
        ))
        connection.execute(text(
            "ALTER TABLE crawl_logs ADD COLUMN IF NOT EXISTS filtered_count INTEGER DEFAULT 0"
        ))
        connection.execute(text(
            "ALTER TABLE boards ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1"
        ))
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_emoji VARCHAR(16)"
        ))
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_color VARCHAR(16)"
        ))

        # 多租戶：監控關鍵字、預警與分析紀錄都要能分辨屬於哪位使用者。
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_code VARCHAR(20) DEFAULT 'free'"
        ))
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP"
        ))
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_count INTEGER DEFAULT 0"
        ))
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP"
        ))
        connection.execute(text(
            "ALTER TABLE watch_keywords ADD COLUMN IF NOT EXISTS user_id INTEGER"
        ))
        connection.execute(text(
            "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS user_id INTEGER"
        ))
        connection.execute(text(
            "ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS user_id INTEGER"
        ))
        for table in ("watch_keywords", "alerts", "analysis_results"):
            connection.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table} (user_id)"
            ))

    _apply_search_indexes()


def _apply_search_indexes():
    """
    說明：
    關鍵字查詢一律用 ILIKE '%關鍵字%'（前後都有萬用字元），
    這種查詢「無法」使用一般 B-tree，也用不到 to_tsvector 的全文索引
    —— 舊的 idx_articles_*_fts 只會拖慢寫入，讀取毫無幫助。

    pg_trgm 的 GIN 索引才真正能加速 ILIKE '%…%'，因此改用它，
    並移除用不到的全文索引。

    這些操作需要建立擴充功能的權限，在部分託管資料庫可能失敗；
    失敗只會讓查詢退回全表掃描（結果仍正確），所以吞掉例外不中斷啟動。
    """

    statements = [
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        "DROP INDEX IF EXISTS idx_articles_title_fts",
        "DROP INDEX IF EXISTS idx_articles_content_fts",
        "CREATE INDEX IF NOT EXISTS idx_articles_title_trgm "
        "ON articles USING gin (title gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS idx_articles_content_trgm "
        "ON articles USING gin (content gin_trgm_ops)",
    ]

    for statement in statements:
        try:
            with engine.begin() as connection:
                connection.execute(text(statement))
        except Exception:
            logger.warning("Search index step skipped: %s", statement[:60])


# 預設方案內容。-1 代表不限制。
# 存進資料表後，日後調整額度不必改程式；這裡只負責「第一次建立」。
DEFAULT_PLANS = [
    {
        "code": "free", "display_name": "免費版", "sort_order": 0,
        "max_watch_keywords": 1, "max_history_days": 7,
        "allow_all_platforms": 0, "monthly_qa_quota": 0, "allow_export": 0,
    },
    {
        "code": "pro", "display_name": "專業版", "sort_order": 1,
        "max_watch_keywords": 5, "max_history_days": 90,
        "allow_all_platforms": 1, "monthly_qa_quota": 100, "allow_export": 1,
    },
    {
        "code": "business", "display_name": "企業版", "sort_order": 2,
        "max_watch_keywords": 20, "max_history_days": -1,
        "allow_all_platforms": 1, "monthly_qa_quota": -1, "allow_export": 1,
    },
]


def _seed_plans(db):
    """建立預設方案；已存在的方案不覆寫，避免蓋掉管理員調整過的額度。"""
    for spec in DEFAULT_PLANS:
        if db.query(Plan).filter(Plan.code == spec["code"]).first() is None:
            db.add(Plan(**spec))


def _backfill_owner(db):
    """把多租戶上線前就存在的資料歸給第一位管理員。

    這些資料建立時系統還沒有「擁有者」的概念，若留成 NULL
    會變成沒有人看得到（查詢一律以登入者過濾）。
    """
    admin = db.query(User).filter(User.role == "admin").order_by(User.id).first()

    if admin is None:
        return

    from app.models.database_models import Alert, WatchKeyword

    for model in (WatchKeyword, Alert):
        db.query(model).filter(model.user_id.is_(None)).update(
            {model.user_id: admin.id}, synchronize_session=False
        )


def _seed_admin_user(db):
    # 說明：
    # users 資料表是空的時候，自動建立預設 admin 帳號。
    # 密碼從環境變數 ADMIN_PASSWORD 讀取；
    # 沒設定時使用 admin123 並發出警告，部署後務必更換。
    if db.query(User).first() is not None:
        return

    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_password:
        admin_password = DEFAULT_ADMIN_PASSWORD
        logger.warning(
            "ADMIN_PASSWORD is not set; default admin account created "
            "with password 'admin123'. Change it in production."
        )

    db.add(User(
        username="admin",
        password_hash=hash_password(admin_password),
        display_name="系統管理員",
        role="admin",
        is_active=1,
    ))


def initialize_database():
    Base.metadata.create_all(bind=engine)
    _apply_schema_migrations()

    db = SessionLocal()

    try:
        platform = get_or_create_platform(db, "ptt")

        for board_name in TARGET_BOARDS:
            board = get_or_create_board(db, platform.id, board_name)
            board.display_name = board_name
            board.url = f"https://www.ptt.cc/bbs/{board_name}/index.html"

        # Dcard 平台與時尚 / 醫美相關看板（醫美 facelift、美妝 makeup、穿搭 dressup）。
        dcard_platform = get_or_create_platform(db, "dcard")
        dcard_platform.display_name = "Dcard"
        dcard_platform.base_url = "https://www.dcard.tw"

        for alias, display_name in DCARD_BOARDS.items():
            board = get_or_create_board(db, dcard_platform.id, alias)
            board.display_name = display_name
            board.url = f"https://www.dcard.tw/f/{alias}"

        # Mobile01 平台與美容 / 時尚相關討論區。
        m01_platform = get_or_create_platform(db, "mobile01")
        m01_platform.display_name = "Mobile01"
        m01_platform.base_url = "https://www.mobile01.com"

        for forum_id, display_name in MOBILE01_BOARDS.items():
            board = get_or_create_board(db, m01_platform.id, forum_id)
            board.display_name = display_name
            board.url = f"https://www.mobile01.com/topiclist.php?f={forum_id}"

        # Threads 平台與目標搜尋關鍵字（Threads 以關鍵字而非看板組織內容）。
        threads_platform = get_or_create_platform(db, "threads")
        threads_platform.display_name = "Threads"
        threads_platform.base_url = "https://www.threads.com"

        for keyword, display_name in THREADS_BOARDS.items():
            board = get_or_create_board(db, threads_platform.id, keyword)
            board.display_name = display_name
            board.url = f"https://www.threads.com/search?q={quote(keyword)}"

        _seed_admin_user(db)
        _seed_plans(db)
        db.commit()

        # 需要 admin 已存在才能歸戶，所以放在 commit 之後。
        _backfill_owner(db)
        db.commit()
    finally:
        db.close()
