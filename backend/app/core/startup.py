# backend/app/core/startup.py

from app.core.database import Base, SessionLocal, engine
from app.models import database_models  # noqa: F401
from app.services.article_service import get_or_create_board, get_or_create_platform
from app.services.dashboard_service import TARGET_BOARDS


def initialize_database():
    Base.metadata.create_all(bind=engine)

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
