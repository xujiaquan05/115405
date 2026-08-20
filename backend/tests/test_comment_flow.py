# backend/tests/test_comment_flow.py

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.database_models import Comment
from app.services.article_service import create_article, save_comments


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _article(db, unique_id="a1"):
    article, _ = create_article(
        db=db, unique_id=unique_id, platform_name="dcard", board_name="makeup",
        author_username="tester", title="測試", content="內容", url=f"http://x/{unique_id}",
    )
    return article


class TestSaveComments:
    def test_saves_with_floor_numbers(self, db):
        article = _article(db)

        saved = save_comments(db, article, ["第一則", "第二則", "第三則"])

        assert saved == 3
        rows = db.query(Comment).order_by(Comment.floor).all()
        assert [row.floor for row in rows] == [1, 2, 3]
        assert rows[0].content == "第一則"
        assert rows[0].sentiment is None  # 尚未評分

    def test_skips_blank_comments(self, db):
        article = _article(db)

        assert save_comments(db, article, ["有內容", "   ", ""]) == 1

    def test_does_not_duplicate_on_recrawl(self, db):
        """重複爬到同一篇文章時，留言不可以被重複寫入。"""
        article = _article(db)
        save_comments(db, article, ["第一則", "第二則"])

        assert save_comments(db, article, ["第一則", "第二則"]) == 0
        assert db.query(Comment).count() == 2

    def test_empty_input(self, db):
        article = _article(db)

        assert save_comments(db, article, []) == 0
        assert save_comments(db, None, ["x"]) == 0

    def test_deleting_article_removes_comments(self, db):
        article = _article(db)
        save_comments(db, article, ["第一則"])

        db.delete(article)
        db.commit()

        assert db.query(Comment).count() == 0
