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


class TestExtractCommentsFromContent:
    """comments 表是後來才加的，之前的文章只把留言併在內文裡，
    重爬也救不回來（文章已存在會被跳過），因此要能從內文還原。"""

    def test_extracts_bullet_lines(self):
        from app.services.article_service import extract_comments_from_content

        content = "主文內容\n【留言】\n- 第一則\n- 第二則"

        assert extract_comments_from_content(content) == ["第一則", "第二則"]

    def test_keeps_multiline_comment_together(self):
        """留言本身可能換行，後續行不可被當成新的一則留言。"""
        from app.services.article_service import extract_comments_from_content

        content = "主文\n【留言】\n- 第一行\n接續的第二行\n- 另一則"

        assert extract_comments_from_content(content) == ["第一行\n接續的第二行", "另一則"]

    def test_no_marker_or_empty(self):
        from app.services.article_service import extract_comments_from_content

        assert extract_comments_from_content("只有主文") == []
        assert extract_comments_from_content("") == []
        assert extract_comments_from_content(None) == []

    def test_ignores_main_content_before_marker(self):
        from app.services.article_service import extract_comments_from_content

        content = "- 這行在標記之前，不是留言\n【留言】\n- 真正的留言"

        assert extract_comments_from_content(content) == ["真正的留言"]


class TestBackfillComments:
    def test_backfills_and_is_idempotent(self, db):
        from app.services.article_service import backfill_comments_from_content

        create_article(
            db=db, unique_id="b1", platform_name="mobile01", board_name="371",
            author_username="tester", title="測試", url="http://x/b1",
            content="主文\n【留言】\n- 留言一\n- 留言二",
        )
        create_article(
            db=db, unique_id="b2", platform_name="mobile01", board_name="371",
            author_username="tester", title="沒有留言", url="http://x/b2",
            content="這篇沒有留言段落",
        )

        result = backfill_comments_from_content(db)

        assert result == {"articles": 1, "comments": 2}
        assert db.query(Comment).count() == 2

        # 重複執行不可重複新增。
        assert backfill_comments_from_content(db) == {"articles": 0, "comments": 0}
        assert db.query(Comment).count() == 2


class TestCommentsBackfillOntoExistingArticles:
    """已存在的文章再次爬到時也要能補上留言。

    PTT 以前不收推文，資料庫裡 9,272 篇 PTT 文章一則留言都沒有。
    若只在「新文章」時才寫留言，這些文章因為 unique_id 已存在而被判為
    skipped，於是永遠補不到——修好爬蟲也救不回舊資料。
    """

    def test_comments_are_written_for_an_article_that_already_exists(self, db):
        article, is_new = create_article(
            db=db,
            unique_id="u1",
            platform_name="ptt",
            board_name="facelift",
            author_username="someone",
            title="音波拉皮心得",
            content="正文",
            url="https://www.ptt.cc/x",
            push_count=3,
        )
        assert is_new is True
        assert save_comments(db, article, []) == 0

        # 第二次爬到同一篇，這次帶了推文。
        again, is_new_again = create_article(
            db=db,
            unique_id="u1",
            platform_name="ptt",
            board_name="facelift",
            author_username="someone",
            title="音波拉皮心得",
            content="正文",
            url="https://www.ptt.cc/x",
            push_count=3,
        )

        assert is_new_again is False
        assert save_comments(db, again, ["推 有效", "噓 沒用"]) == 2

    def test_a_second_pass_does_not_duplicate_them(self, db):
        article, _ = create_article(
            db=db,
            unique_id="u2",
            platform_name="ptt",
            board_name="facelift",
            author_username="someone",
            title="標題",
            content="正文",
            url="https://www.ptt.cc/y",
            push_count=0,
        )
        save_comments(db, article, ["推 好"])

        assert save_comments(db, article, ["推 好", "噓 壞"]) == 0
