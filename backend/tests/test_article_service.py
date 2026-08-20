# backend/tests/test_article_service.py

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.services.article_service import create_article


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _make(db, unique_id, published_at):
    article, is_new = create_article(
        db=db,
        unique_id=unique_id,
        platform_name="threads",
        board_name="醫美",
        author_username="tester",
        title="測試貼文",
        content="內容",
        url=f"http://x/{unique_id}",
        published_at=published_at,
    )
    return article, is_new


class TestPublishedAtFallback:
    """來源站台抓不到發文時間時，published_at 不可留 NULL：
    儀表板所有查詢都會過濾日期區間，NULL 會讓文章永遠不出現，
    也不會被排進情緒評分佇列。"""

    def test_missing_published_at_is_filled(self, db):
        article, is_new = _make(db, "a1", None)

        assert is_new is True
        assert article.published_at is not None

    def test_given_published_at_is_kept(self, db):
        from datetime import datetime

        moment = datetime(2026, 8, 17, 16, 43)
        article, _ = _make(db, "a2", moment)

        assert article.published_at == moment

    def test_duplicate_unique_id_not_recreated(self, db):
        _make(db, "a3", None)
        _article, is_new = _make(db, "a3", None)

        assert is_new is False
