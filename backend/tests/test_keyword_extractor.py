# backend/tests/test_keyword_extractor.py

from app.services.keyword_extractor import extract_keywords


class TestExtractKeywords:
    def test_counts_domain_terms(self):
        texts = [
            "玻尿酸打完覺得很自然",
            "玻尿酸的價格好高",
            "雷射術後恢復期",
        ]
        result = extract_keywords(texts, top_n=10)
        by_word = {r["keyword"]: r["count"] for r in result}

        # 「玻尿酸」出現在兩篇 → count 2，且不被切碎（已加入 jieba 詞庫）。
        assert by_word.get("玻尿酸") == 2
        assert "雷射" in by_word

    def test_filters_stopwords_and_short_tokens(self):
        result = extract_keywords(["我覺得這個真的很好"], top_n=20)
        words = [r["keyword"] for r in result]
        # 停用詞不應出現
        assert "覺得" not in words
        assert "真的" not in words
        assert "的" not in words

    def test_filters_pure_ascii_and_numbers(self):
        result = extract_keywords(["PTT 2024 玻尿酸 https://x.com"], top_n=20)
        words = [r["keyword"] for r in result]
        assert "玻尿酸" in words
        assert all("PTT" != w and "2024" != w for w in words)

    def test_top_n_limit(self):
        texts = [f"關鍵字{i} 測試詞{i}" for i in range(50)]
        result = extract_keywords(texts, top_n=5)
        assert len(result) <= 5

    def test_empty_input(self):
        assert extract_keywords([], top_n=10) == []
        assert extract_keywords(["", None], top_n=10) == []

    def test_result_sorted_desc(self):
        texts = ["玻尿酸 玻尿酸 玻尿酸", "肉毒 肉毒", "雷射"]
        result = extract_keywords(texts, top_n=10)
        counts = [r["count"] for r in result]
        assert counts == sorted(counts, reverse=True)
