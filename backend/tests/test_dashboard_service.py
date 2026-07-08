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
        # Query dùng ilike %term%, term rỗng nghĩa là match tất cả.
        assert split_keyword_terms("") == [""]
        assert split_keyword_terms(None) == [""]
