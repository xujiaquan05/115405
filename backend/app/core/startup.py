# backend/app/core/startup.py

import logging
import os

from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.models import database_models  # noqa: F401
from app.models.database_models import User
from app.services.article_service import get_or_create_board, get_or_create_platform
from app.services.auth_service import hash_password
from app.services.dashboard_service import TARGET_BOARDS


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

        _seed_admin_user(db)

        db.commit()
    finally:
        db.close()
