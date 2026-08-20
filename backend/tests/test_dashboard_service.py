# backend/tests/test_dashboard_service.py

from app.services.dashboard_service import split_keyword_terms


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
