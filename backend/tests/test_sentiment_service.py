# backend/tests/test_sentiment_service.py

import json

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
