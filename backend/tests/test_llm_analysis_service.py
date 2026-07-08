# backend/tests/test_llm_analysis_service.py

from app.services.llm_analysis_service import (
    PROMPT_CACHE_VERSION,
    build_cache_analysis_type,
)


class TestBuildCacheAnalysisType:
    def test_no_boards_includes_prompt_version(self):
        key = build_cache_analysis_type("overview")

        assert key == f"overview:{PROMPT_CACHE_VERSION}"

    def test_key_never_exceeds_column_limit(self):
        key = build_cache_analysis_type("a" * 100, ["facelift", "BeautySalon"])

        assert len(key) <= 50

    def test_board_order_does_not_change_key(self):
        first = build_cache_analysis_type("overview", ["facelift", "BeautySalon"])
        second = build_cache_analysis_type("overview", ["BeautySalon", "facelift"])

        assert first == second

    def test_different_boards_different_key(self):
        first = build_cache_analysis_type("overview", ["facelift"])
        second = build_cache_analysis_type("overview", ["BeautySalon"])

        assert first != second
