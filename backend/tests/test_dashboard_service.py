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
