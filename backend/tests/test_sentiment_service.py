# backend/tests/test_sentiment_service.py

import json
import re
from types import SimpleNamespace

import pytest

from app.services import sentiment_service
from app.services.llm_client import LLMServiceUnavailableError
from app.services.sentiment_service import _parse_batch_response


class TestParseBatchResponse:
    def test_valid_response(self):
        raw = json.dumps({
            "results": [
                {"id": 1, "sentiment": "positive"},
                {"id": 2, "sentiment": "negative"},
                {"id": 3, "sentiment": "neutral"},
            ]
        })

        assert _parse_batch_response(raw) == {
            1: "positive",
            2: "negative",
            3: "neutral",
        }

    def test_uppercase_label_normalized(self):
        raw = json.dumps({"results": [{"id": 1, "sentiment": "NEGATIVE"}]})

        assert _parse_batch_response(raw) == {1: "negative"}

    def test_invalid_label_dropped(self):
        raw = json.dumps({
            "results": [
                {"id": 1, "sentiment": "angry"},
                {"id": 2, "sentiment": "positive"},
            ]
        })

        assert _parse_batch_response(raw) == {2: "positive"}

    def test_string_id_dropped(self):
        raw = json.dumps({"results": [{"id": "1", "sentiment": "positive"}]})

        assert _parse_batch_response(raw) == {}

    def test_invalid_json(self):
        assert _parse_batch_response("not json {") == {}
        assert _parse_batch_response(None) == {}

    def test_results_not_list(self):
        raw = json.dumps({"results": "positive"})

        assert _parse_batch_response(raw) == {}

    def test_non_dict_items_ignored(self):
        raw = json.dumps({"results": ["positive", {"id": 5, "sentiment": "neutral"}]})

        assert _parse_batch_response(raw) == {5: "neutral"}


class TestExcerptForScoring:
    """中文心得文的結論通常在最後，只取開頭會把情緒最明確的段落切掉，
    實測會把正面心得誤判成 neutral，因此改成頭尾都取。"""

    def test_short_content_unchanged(self):
        from app.services.sentiment_service import _excerpt_for_scoring

        assert _excerpt_for_scoring("這罐很好用") == "這罐很好用"

    def test_long_content_keeps_head_and_tail(self):
        from app.services.sentiment_service import (
            CONTENT_HEAD_CHARS,
            CONTENT_TAIL_CHARS,
            _excerpt_for_scoring,
        )

        head = "開" * CONTENT_HEAD_CHARS
        middle = "中" * 500
        tail = "值得推薦" + "尾" * (CONTENT_TAIL_CHARS - 4)
        result = _excerpt_for_scoring(head + middle + tail)

        assert result.startswith("開")
        assert result.endswith("尾")
        assert "值得推薦" in result          # 結論必須保留
        assert "……" in result               # 中間省略要標示
        # 「……」是兩個字元（U+2026 ×2）。
        assert len(result) == CONTENT_HEAD_CHARS + CONTENT_TAIL_CHARS + len("……")

    def test_drops_comment_section(self):
        """文章情緒指的是發文者本人；留言是別人的意見，且已另存 comments 表。"""
        from app.services.sentiment_service import _excerpt_for_scoring

        content = "發文者的內容\n【留言】\n- 這間超雷\n- 不推"

        assert _excerpt_for_scoring(content) == "發文者的內容"

    def test_tail_comes_from_poster_not_comments(self):
        from app.services.sentiment_service import _excerpt_for_scoring

        content = "背" * 400 + "我的結論是很滿意" + "\n【留言】\n- " + "雷" * 300

        result = _excerpt_for_scoring(content)

        assert result.endswith("我的結論是很滿意")
        assert "雷" not in result

    def test_empty(self):
        from app.services.sentiment_service import _excerpt_for_scoring

        assert _excerpt_for_scoring(None) == ""
        assert _excerpt_for_scoring("") == ""


class TestBlockedBatchFallback:
    """整批被 Gemini 安全機制擋下時的處理。

    實測：補評分舊文章時，有 1,074 篇卡住評不出來。
    追下去發現 API 回 200 但 response.text 是 None，
    prompt_feedback 顯示 block_reason=PROHIBITED_CONTENT——
    同一批 20 篇裡只要一篇踩到安全機制，整個 prompt 就被擋，
    另外 19 篇正常文章跟著拿不到結果，而且下次還會挑到同一批。
    """

    def _articles(self, count: int):
        return [SimpleNamespace(id=index, title=f"t{index}", content="c") for index in range(count)]

    def test_returns_the_parsed_result_when_nothing_is_blocked(self, monkeypatch):
        monkeypatch.setattr(
            sentiment_service,
            "generate_json_response",
            lambda _prompt: '{"results": [{"id": 0, "sentiment": "positive"}]}',
        )

        assert sentiment_service._score_batch(self._articles(1)) == {0: "positive"}

    def test_splits_the_batch_so_one_blocked_article_does_not_sink_the_rest(self, monkeypatch):
        blocked_id = 2

        def fake_generate(prompt):
            # 只要這一批含有問題文章，整批就回空——模擬真實的 block 行為。
            if f'"id": {blocked_id}' in prompt:
                return ""

            # 只看「文章列表：」之後的內容：prompt 的格式說明裡有個
            # {"id": 123} 範例，整段一起抓會多出一個不存在的文章。
            article_list = prompt.split("文章列表：")[-1]
            ids = re.findall(r'"id": (\d+)', article_list)
            results = ", ".join(f'{{"id": {i}, "sentiment": "neutral"}}' for i in ids)
            return f'{{"results": [{results}]}}'

        monkeypatch.setattr(sentiment_service, "generate_json_response", fake_generate)

        result = sentiment_service._score_batch(self._articles(4))

        # 另外三篇照樣評到分，只有那一篇被標記起來。
        assert result == {
            0: "neutral",
            1: "neutral",
            blocked_id: sentiment_service.BLOCKED_SENTIMENT,
            3: "neutral",
        }

    def test_a_single_blocked_article_is_marked_so_it_is_not_retried_forever(self, monkeypatch):
        monkeypatch.setattr(sentiment_service, "generate_json_response", lambda _prompt: "")

        result = sentiment_service._score_batch(self._articles(1))

        assert result == {0: sentiment_service.BLOCKED_SENTIMENT}

    def test_quota_errors_stop_the_run_instead_of_splitting(self, monkeypatch):
        calls = []

        def fake_generate(prompt):
            calls.append(prompt)
            raise LLMServiceUnavailableError("quota")

        monkeypatch.setattr(sentiment_service, "generate_json_response", fake_generate)

        with pytest.raises(LLMServiceUnavailableError):
            sentiment_service._score_batch(self._articles(8))

        # 額度用完時再拆下去只是白白多打幾次，必須第一次就停。
        assert len(calls) == 1
