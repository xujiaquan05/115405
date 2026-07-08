# backend/tests/test_rag_service.py

from app.services.rag_service import _fallback_intent, _safe_json


class TestSafeJson:
    def test_valid_json(self):
        assert _safe_json('{"a": 1}', {}) == {"a": 1}

    def test_invalid_json_returns_fallback(self):
        fallback = {"answer": "fallback"}
        assert _safe_json("not json {", fallback) is fallback


class TestFallbackIntent:
    def test_known_keyword_and_negative_sentiment(self):
        intent = _fallback_intent("玻尿酸有哪些負評？")

        assert "玻尿酸" in intent["keywords"]
        assert intent["sentiment"] == "negative"
        assert intent["days"] == 30

    def test_positive_sentiment(self):
        intent = _fallback_intent("肉毒有什麼推薦的好評嗎")

        assert intent["sentiment"] == "positive"

    def test_week_range(self):
        intent = _fallback_intent("一週內雷射的討論")

        assert intent["days"] == 7
        assert "雷射" in intent["keywords"]

    def test_three_month_range(self):
        intent = _fallback_intent("三個月來音波的變化")

        assert intent["days"] == 90
        assert intent["question_type"] == "trend"

    def test_count_question(self):
        intent = _fallback_intent("診所相關文章有幾篇")

        assert intent["question_type"] == "count"

    def test_unknown_keyword_still_returns_keywords(self):
        intent = _fallback_intent("隆乳手術安全嗎")

        assert intent["keywords"], "keywords 不可為空"
