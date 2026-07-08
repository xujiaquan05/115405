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
