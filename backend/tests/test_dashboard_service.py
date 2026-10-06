# backend/tests/test_dashboard_service.py

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.services.dashboard_service import split_keyword_terms


@pytest.fixture
def db_session():
    """獨立的 SQLite in-memory session，不會碰到真正的資料庫。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


class TestSplitKeywordTerms:
    def test_single_keyword(self):
        assert split_keyword_terms("玻尿酸") == ["玻尿酸"]

    def test_space_separated(self):
        assert split_keyword_terms("玻尿酸 肉毒") == ["玻尿酸", "肉毒"]

    def test_chinese_comma_and_enumeration(self):
        assert split_keyword_terms("玻尿酸，肉毒、雷射") == ["玻尿酸", "肉毒", "雷射"]

    def test_empty_returns_single_empty_term(self):
        # 查詢用 ilike %term%，term 為空字串表示 match 全部。
        assert split_keyword_terms("") == [""]
        assert split_keyword_terms(None) == [""]


class TestBoardFilterAcrossPlatforms:
    """迴歸測試：沒指定看板時不可只留 PTT，否則 Dcard / Mobile01 / Threads
    的文章會整批從儀表板消失（實測曾少算 27 / 61 篇）。"""

    def test_no_boards_means_all_platforms(self):
        from app.services.dashboard_service import normalize_filter_boards

        assert normalize_filter_boards(None) == []
        assert normalize_filter_boards([]) == []

    def test_accepts_non_ptt_board_names(self):
        from app.services.dashboard_service import normalize_filter_boards

        # Mobile01 用編號、Threads 用中文關鍵字，都必須被保留。
        assert normalize_filter_boards(["371", "醫美"]) == ["371", "醫美"]

    def test_cleans_and_dedupes(self):
        from app.services.dashboard_service import normalize_filter_boards

        assert normalize_filter_boards([" makeup ", "makeup", "", None]) == ["makeup"]


class TestPlatformQualifiedBoardFilter:
    """PTT 與 Dcard 都有 facelift 看板，只用看板名稱會混到另一個平台的文章，
    因此篩選支援 '平台:看板' 形式。"""

    def test_normalize_keeps_platform_prefix(self):
        from app.services.dashboard_service import normalize_filter_boards

        assert normalize_filter_boards(["dcard:facelift"]) == ["dcard:facelift"]

    def test_filter_separates_same_named_boards(self, db_session):
        from app.models.database_models import Article, Board, Platform
        from app.services.dashboard_service import apply_board_filter

        ptt = Platform(name="ptt")
        dcard = Platform(name="dcard")
        db_session.add_all([ptt, dcard])
        db_session.flush()

        ptt_board = Board(platform_id=ptt.id, name="facelift", is_active=1)
        dcard_board = Board(platform_id=dcard.id, name="facelift", is_active=1)
        db_session.add_all([ptt_board, dcard_board])
        db_session.flush()

        db_session.add_all([
            Article(unique_id="p1", platform_id=ptt.id, board_id=ptt_board.id, title="ptt 文", url="u1"),
            Article(unique_id="d1", platform_id=dcard.id, board_id=dcard_board.id, title="dcard 文", url="u2"),
        ])
        db_session.commit()

        query = db_session.query(Article)
        assert apply_board_filter(query, ["dcard:facelift"]).count() == 1
        assert apply_board_filter(query, ["ptt:facelift"]).count() == 1
        # 不指定平台時兩篇都算；不指定看板時也是全部。
        assert apply_board_filter(query, ["facelift"]).count() == 2
        assert apply_board_filter(query, None).count() == 2

    def test_excel_export_respects_platform_and_legacy_board_filters(self, db_session):
        from app.core.time_utils import taiwan_now
        from app.models.database_models import Article, Board, Platform
        from app.services.export_service import build_articles_xlsx, get_export_articles

        for name in ("ptt", "dcard"):
            platform = Platform(name=name)
            db_session.add(platform)
            db_session.flush()
            board = Board(platform_id=platform.id, name="facelift", is_active=1)
            db_session.add(board)
            db_session.flush()
            db_session.add(Article(
                unique_id=name, platform_id=platform.id, board_id=board.id,
                title=f"玻尿酸 {name}", url=f"https://example.test/{name}", published_at=taiwan_now(),
            ))
        db_session.commit()

        rows = get_export_articles(db_session, "玻尿酸", boards=["ptt:facelift"])
        assert [row.unique_id for row in rows] == ["ptt"]
        assert len(get_export_articles(db_session, "玻尿酸", boards=["facelift"])) == 2
        from io import BytesIO
        from zipfile import ZipFile

        with ZipFile(BytesIO(build_articles_xlsx(rows))) as workbook:
            sheet = workbook.read("xl/worksheets/sheet1.xml").decode()
        assert "ptt" in sheet
        assert "dcard" not in sheet


class TestHotArticleCounts:
    """熱門文章列表有兩個數字，意義不同，不能混用。

    push_count 是各平台自己的互動指標（PTT 推文數、Dcard 讚數、
    Mobile01 回覆數、Threads 取讚/回覆/轉發最大值），跨平台不可比；
    comment_count 是本系統實際抓回的留言筆數，四個平台口徑一致。
    畫面上曾把 push_count 標成「回文數」，所以這裡把兩者各自釘住。
    """

    def _article(self, db_session, title, push_count):
        from datetime import datetime

        from app.models.database_models import Article, Platform

        platform = db_session.query(Platform).filter(Platform.name == "ptt").first()
        if platform is None:
            platform = Platform(name="ptt")
            db_session.add(platform)
            db_session.flush()

        article = Article(
            unique_id=f"test-{title}",
            platform_id=platform.id,
            title=title,
            content="內容",
            push_count=push_count,
            published_at=datetime(2026, 1, 1),
        )
        db_session.add(article)
        db_session.commit()
        return article

    def test_comment_count_is_the_number_of_comments_actually_stored(self, db_session):
        from app.models.database_models import Comment
        from app.services.dashboard_service import get_hot_articles

        article = self._article(db_session, "音波拉皮心得", push_count=3)
        for floor in range(4):
            db_session.add(Comment(article_id=article.id, floor=floor, content=f"留言{floor}"))
        db_session.commit()

        row = next(
            a for a in get_hot_articles(db_session, keyword="音波", days=36500)
            if a["id"] == article.id
        )

        # push_count 來自平台，comment_count 來自我們自己的 comments 表。
        assert row["push_count"] == 3
        assert row["comment_count"] == 4

    def test_an_article_with_no_comments_reports_zero_not_missing(self, db_session):
        from app.services.dashboard_service import get_hot_articles

        article = self._article(db_session, "電波拉皮詢問", push_count=1)

        row = next(
            a for a in get_hot_articles(db_session, keyword="電波", days=36500)
            if a["id"] == article.id
        )

        assert row["comment_count"] == 0
