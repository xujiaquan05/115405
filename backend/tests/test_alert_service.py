# backend/tests/test_alert_service.py

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.database_models import Article, Board, Platform, WatchKeyword, Alert
from app.services import alert_service


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    platform = Platform(name="ptt")
    session.add(platform)
    session.flush()
    board = Board(platform_id=platform.id, name="facelift")
    session.add(board)
    session.flush()

    yield session, platform, board
    session.close()


def _add_articles(session, platform, board, positive=0, negative=0, neutral=0):
    idx = 0
    for _n, sentiment in [(positive, "positive"), (negative, "negative"), (neutral, "neutral")]:
        for _ in range(_n):
            idx += 1
            session.add(Article(
                unique_id=f"u{sentiment}{idx}",
                platform_id=platform.id,
                board_id=board.id,
                title=f"玻尿酸討論 {idx}",
                content="玻尿酸相關內容",
                url=f"http://x/{sentiment}/{idx}",
                push_count=5,
                sentiment=sentiment,
                published_at=datetime.utcnow(),
            ))
    session.commit()


class TestEvaluateKeyword:
    def test_high_negative_is_critical(self, db):
        session, platform, board = db
        # 8 負 / 2 正 → 負面 80% → critical
        _add_articles(session, platform, board, positive=2, negative=8)

        result = alert_service.evaluate_keyword(session, "玻尿酸", 30)
        assert result["level"] == "critical"
        assert result["article_count"] == 10
        assert result["negative_ratio"] >= 40

    def test_medium_negative_is_warning(self, db):
        session, platform, board = db
        # 3 負 / 7 正 → 負面 30% → warning
        _add_articles(session, platform, board, positive=7, negative=3)

        result = alert_service.evaluate_keyword(session, "玻尿酸", 30)
        assert result["level"] == "warning"

    def test_low_negative_no_alert(self, db):
        session, platform, board = db
        _add_articles(session, platform, board, positive=9, negative=1)

        result = alert_service.evaluate_keyword(session, "玻尿酸", 30)
        assert result["level"] is None

    def test_too_few_articles_no_alert(self, db):
        session, platform, board = db
        # 只有 2 篇（低於 MIN_ARTICLES）即使全負面也不預警
        _add_articles(session, platform, board, negative=2)

        result = alert_service.evaluate_keyword(session, "玻尿酸", 30)
        assert result["level"] is None


class TestRunAlertChecks:
    def test_creates_alert_for_watched_keyword(self, db):
        session, platform, board = db
        _add_articles(session, platform, board, positive=2, negative=8)
        session.add(WatchKeyword(keyword="玻尿酸", days=30, enabled=1))
        session.commit()

        created = alert_service.run_alert_checks(session)
        assert len(created) == 1
        assert created[0].keyword == "玻尿酸"
        assert created[0].level == "critical"

    def test_disabled_keyword_skipped(self, db):
        session, platform, board = db
        _add_articles(session, platform, board, positive=2, negative=8)
        session.add(WatchKeyword(keyword="玻尿酸", days=30, enabled=0))
        session.commit()

        created = alert_service.run_alert_checks(session)
        assert len(created) == 0

    def test_dedupe_no_duplicate_within_window(self, db):
        session, platform, board = db
        _add_articles(session, platform, board, positive=2, negative=8)
        session.add(WatchKeyword(keyword="玻尿酸", days=30, enabled=1))
        session.commit()

        first = alert_service.run_alert_checks(session)
        second = alert_service.run_alert_checks(session)
        assert len(first) == 1
        assert len(second) == 0  # 12 小時內不重複
