# backend/tests/test_sentiment_score.py

from app.routers.analysis import compute_sentiment_score


class TestComputeSentimentScore:
    def test_all_positive_is_100(self):
        assert compute_sentiment_score({"positive": 100, "negative": 0}) == 100

    def test_all_negative_is_0(self):
        assert compute_sentiment_score({"positive": 0, "negative": 100}) == 0

    def test_all_neutral_is_50(self):
        assert compute_sentiment_score({"positive": 0, "negative": 0}) == 50

    def test_balanced_is_50(self):
        # 正負各半 → 中性 50。
        assert compute_sentiment_score({"positive": 50, "negative": 50}) == 50

    def test_mostly_positive(self):
        # 80% 正、10% 負 → 50 + (80-10)/2 = 85。
        assert compute_sentiment_score({"positive": 80, "negative": 10}) == 85

    def test_mostly_negative(self):
        # 20% 正、60% 負 → 50 + (20-60)/2 = 30。
        assert compute_sentiment_score({"positive": 20, "negative": 60}) == 30

    def test_missing_keys_default_to_neutral(self):
        assert compute_sentiment_score({}) == 50

    def test_result_is_clamped_and_int(self):
        score = compute_sentiment_score({"positive": 100, "negative": 0})
        assert isinstance(score, int)
        assert 0 <= score <= 100
