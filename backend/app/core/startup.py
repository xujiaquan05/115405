# backend/app/core/startup.py

import logging
import os
from urllib.parse import quote

from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.models import database_models  # noqa: F401
from app.models.database_models import User
from app.services.article_service import get_or_create_board, get_or_create_platform
from app.services.auth_service import hash_password
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


def _seed_admin_user(db):
    # 說明：
    # users 資料表是空的時候，自動建立預設 admin 帳號。
    # 密碼從環境變數 ADMIN_PASSWORD 讀取；
    # 沒設定時使用 admin123 並發出警告，部署後務必更換。
    if db.query(User).first() is not None:
        return

    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_password:
        admin_password = "admin123"
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

        db.commit()
    finally:
        db.close()
