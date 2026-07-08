# backend/app/core/startup.py

from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.models import database_models  # noqa: F401
from app.services.article_service import get_or_create_board, get_or_create_platform
from app.services.dashboard_service import TARGET_BOARDS


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

        db.commit()
    finally:
        db.close()
