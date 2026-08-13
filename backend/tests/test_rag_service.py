# backend/tests/test_rag_service.py

from app.services import rag_service
from app.services.cache_service import CACHE_STORE
from app.services.rag_service import (
    _fallback_intent,
    _format_history,
    _qa_cache_key,
    _safe_json,
    answer_question,
)


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

    def test_platform_detection(self):
        assert _fallback_intent("Dcard 上玻尿酸的負評").get("platform") == "dcard"
        assert _fallback_intent("PTT 上肉毒討論").get("platform") == "ptt"
        assert _fallback_intent("玻尿酸有哪些負評").get("platform") == "all"


class TestFormatHistory:
    def test_empty_returns_blank(self):
        assert _format_history(None) == ""
        assert _format_history([]) == ""

    def test_builds_recent_turns_and_labels_roles(self):
        history = [
            {"role": "user", "content": "玻尿酸有負評嗎"},
            {"role": "assistant", "content": "有一些關於術後腫脹的抱怨"},
        ]
        text = _format_history(history)
        assert "使用者：玻尿酸有負評嗎" in text
        assert "AI：有一些關於術後腫脹的抱怨" in text

    def test_limits_to_last_turns(self):
        history = [{"role": "user", "content": f"問題{i}"} for i in range(10)]
        text = _format_history(history, max_turns=3)
        assert "問題9" in text and "問題7" in text
        assert "問題0" not in text


class TestQaCacheKey:
    def test_same_inputs_same_key(self):
        a = _qa_cache_key("玻尿酸負評", {"keyword": "玻尿酸", "days": 30}, None)
        b = _qa_cache_key("玻尿酸負評", {"keyword": "玻尿酸", "days": 30}, None)
        assert a == b

    def test_different_question_different_key(self):
        a = _qa_cache_key("玻尿酸負評", {"keyword": "玻尿酸", "days": 30}, None)
        b = _qa_cache_key("肉毒負評", {"keyword": "玻尿酸", "days": 30}, None)
        assert a != b

    def test_history_changes_key(self):
        ctx = {"keyword": "玻尿酸", "days": 30}
        a = _qa_cache_key("那負面的呢", ctx, [{"role": "user", "content": "有好評嗎"}])
        b = _qa_cache_key("那負面的呢", ctx, [{"role": "user", "content": "有壞評嗎"}])
        assert a != b


class TestAnswerQuestionCache:
    def test_second_call_hits_cache(self, monkeypatch):
        CACHE_STORE.clear()
        calls = {"n": 0}

        def fake_generate(question, dashboard_context, history=None):
            calls["n"] += 1
            return {"answer": "答案", "key_points": [], "marketing_action": "", "confidence": "high"}

        monkeypatch.setattr(rag_service, "generate_dashboard_context_answer", fake_generate)

        ctx = {"keyword": "玻尿酸", "days": 30, "hot_articles": []}
        first = answer_question(db=None, question="風險在哪", dashboard_context=ctx)
        second = answer_question(db=None, question="風險在哪", dashboard_context=ctx)

        assert calls["n"] == 1              # 第二次走快取，沒再呼叫 LLM
        assert first["cached"] is False
        assert second["cached"] is True

    def test_no_cache_forces_regenerate(self, monkeypatch):
        CACHE_STORE.clear()
        calls = {"n": 0}

        def fake_generate(question, dashboard_context, history=None):
            calls["n"] += 1
            return {"answer": "答案", "key_points": [], "marketing_action": "", "confidence": "high"}

        monkeypatch.setattr(rag_service, "generate_dashboard_context_answer", fake_generate)

        ctx = {"keyword": "玻尿酸", "days": 30, "hot_articles": []}
        answer_question(db=None, question="風險在哪", dashboard_context=ctx)
        answer_question(db=None, question="風險在哪", dashboard_context=ctx, use_cache=False)

        assert calls["n"] == 2              # use_cache=False 強制重新生成
