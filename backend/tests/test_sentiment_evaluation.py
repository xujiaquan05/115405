# backend/tests/test_sentiment_evaluation.py

"""評估指標本身的正確性。

指標算錯會讓整份成效報告失去意義，因此用手算得出答案的小例子驗證。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from evaluate_sentiment import accuracy, confusion_matrix, per_class_metrics  # noqa: E402


def _item(gold, model):
    return {"gold_label": gold, "model_label": model, "title": "t", "set": "random"}


class TestAccuracy:
    def test_all_correct(self):
        assert accuracy([_item("positive", "positive"), _item("neutral", "neutral")]) == 1.0

    def test_half_correct(self):
        assert accuracy([_item("positive", "positive"), _item("neutral", "negative")]) == 0.5

    def test_empty_does_not_divide_by_zero(self):
        assert accuracy([]) == 0.0


class TestPerClassMetrics:
    def test_precision_recall_f1(self):
        # negative：模型判 2 篇，其中 1 篇正確；實際有 2 篇負面
        # -> precision 1/2 = 0.5、recall 1/2 = 0.5、F1 = 0.5
        items = [
            _item("negative", "negative"),
            _item("neutral", "negative"),
            _item("negative", "neutral"),
            _item("neutral", "neutral"),
        ]

        stats = per_class_metrics(items)["negative"]

        assert stats["support"] == 2
        assert stats["precision"] == 0.5
        assert stats["recall"] == 0.5
        assert stats["f1"] == 0.5

    def test_class_never_predicted_scores_zero(self):
        """模型從不預測某類別時，precision 分母為 0，不可拋例外。"""
        items = [_item("positive", "neutral"), _item("neutral", "neutral")]

        stats = per_class_metrics(items)["positive"]

        assert stats["precision"] == 0.0
        assert stats["recall"] == 0.0
        assert stats["f1"] == 0.0


class TestConfusionMatrix:
    def test_counts_by_gold_then_prediction(self):
        items = [
            _item("neutral", "negative"),
            _item("neutral", "negative"),
            _item("neutral", "neutral"),
        ]

        matrix = confusion_matrix(items)

        assert matrix["neutral"]["negative"] == 2
        assert matrix["neutral"]["neutral"] == 1
        assert matrix["positive"]["positive"] == 0
