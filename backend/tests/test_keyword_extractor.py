# backend/tests/test_keyword_extractor.py

"""熱門話題的斷詞規則與排序規則。

排行榜曾經是純詞頻，前 20 名有 8 個是「還是」「就是」「起來」這類虛詞。
現在改成比「在這批文章的普及程度」對上「在全庫的普及程度」，
並要求一個詞至少被兩篇文章提到才算話題。

底下前半是原有的斷詞／過濾測試（因為新規則而改用兩篇文章，
意圖不變：詞不能被切碎、停用詞與純英數要濾掉）；
後半是排序規則的測試。
"""

from app.services.keyword_extractor import extract_keywords


class TestExtractKeywords:
    def test_counts_domain_terms(self):
        texts = [
            "玻尿酸打完覺得很自然",
            "玻尿酸的價格好高",
            "雷射術後恢復期",
            "雷射價格與恢復期",
        ]
        result = extract_keywords(texts, top_n=10)
        by_word = {r["keyword"]: r["count"] for r in result}

        # 「玻尿酸」出現在兩篇 → count 2，且不被切碎（已加入 jieba 詞庫）。
        assert by_word.get("玻尿酸") == 2
        assert "雷射" in by_word

    def test_filters_stopwords_and_short_tokens(self):
        result = extract_keywords(["我覺得這個真的很好", "我覺得這個真的很好"], top_n=20)
        words = [r["keyword"] for r in result]
        # 停用詞不應出現
        assert "覺得" not in words
        assert "真的" not in words
        assert "的" not in words

    def test_filters_pure_ascii_and_numbers(self):
        texts = ["PTT 2024 玻尿酸 https://x.com", "PTT 2024 玻尿酸 https://x.com"]
        result = extract_keywords(texts, top_n=20)
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
        texts = ["玻尿酸 玻尿酸 玻尿酸", "玻尿酸 肉毒", "肉毒 雷射", "雷射 玻尿酸"]
        result = extract_keywords(texts, top_n=10)
        counts = [r["count"] for r in result]
        assert counts == sorted(counts, reverse=True)


class TestWordsCommonEverywhereAreDemoted:
    def test_the_rarer_domain_term_outranks_the_common_one(self):
        # 兩個詞在這批文章裡一樣普及：四篇都有。
        texts = [
            "還是 玻尿酸 保濕",
            "還是 玻尿酸 保濕",
            "還是 玻尿酸 保濕",
            "還是 玻尿酸 保濕",
        ]
        # 但「玻尿酸」在全庫只有少數篇提到，「保濕」則相當常見。
        corpus = {"玻尿酸": 40, "保濕": 300}

        ranked = extract_keywords(
            texts, top_n=5, corpus_document_frequency=corpus, corpus_size=1000
        )
        order = [row["keyword"] for row in ranked]

        assert order.index("玻尿酸") < order.index("保濕")
        # 「還是」根本不是領域詞，連進榜的機會都沒有。
        assert "還是" not in order

    def test_without_corpus_stats_it_falls_back_to_document_count(self):
        texts = ["玻尿酸 保濕", "玻尿酸", "玻尿酸"]

        ranked = extract_keywords(texts, top_n=5)

        assert ranked[0]["keyword"] == "玻尿酸"
        assert ranked[0]["count"] == 3


class TestATopicMustAppearInTwoPosts:
    def test_a_word_in_a_single_article_is_not_a_topic(self):
        # 斷詞偶爾會切出「還掰說」這種碎片，只在一篇出現。
        texts = ["玻尿酸 還掰說", "玻尿酸 保濕"]

        keywords = [row["keyword"] for row in extract_keywords(texts, top_n=10)]

        assert "玻尿酸" in keywords
        assert "還掰說" not in keywords
        assert "保濕" not in keywords

    def test_one_matching_article_yields_nothing_rather_than_noise(self):
        # 查到的文章只有一篇時，每個詞都只出現一次，排序純屬雜訊。
        assert extract_keywords(["玻尿酸 保濕 效果 推薦"], top_n=20) == []

    def test_no_articles_at_all(self):
        assert extract_keywords([], top_n=20) == []


class TestCountIsArticlesNotOccurrences:
    def test_count_does_not_inflate_when_one_article_repeats_a_word(self):
        # 畫面上寫「N 則」，所以 count 必須是篇數；
        # 否則一篇狂刷同一個詞的長文就能灌爆排行榜。
        texts = ["玻尿酸 玻尿酸 玻尿酸 玻尿酸 玻尿酸", "玻尿酸 保濕", "保濕 效果"]

        counts = {row["keyword"]: row["count"] for row in extract_keywords(texts, top_n=10)}

        assert counts["玻尿酸"] == 2
        assert counts["保濕"] == 2


class TestOnlyDomainTermsAppear:
    """熱門話題要回答「大家在討論哪些醫美項目」，不是「用了哪些中文詞」。

    純統計時排行榜出現過「留言」「大學」「昨天」「在意」，
    它們確實常出現，但對輿情分析沒有意義。
    """

    def test_everyday_words_are_dropped_even_when_very_common(self):
        texts = ["留言 大學 昨天 在意 玻尿酸"] * 5

        keywords = [row["keyword"] for row in extract_keywords(texts, top_n=20)]

        assert keywords == ["玻尿酸"]

    def test_multi_character_terms_survive_segmentation(self):
        # 詞庫同時餵給 jieba，否則「玻尿酸」會被切成「玻」「尿酸」而比對不到。
        texts = ["打了玻尿酸跟皮秒雷射", "玻尿酸跟皮秒雷射都做過"]

        keywords = [row["keyword"] for row in extract_keywords(texts, top_n=20)]

        assert "玻尿酸" in keywords
        assert "皮秒雷射" in keywords

    def test_generic_review_words_are_deliberately_excluded(self):
        # 「效果」「價格」任何商品都談得到，收進詞庫會穩居第一卻沒有資訊量。
        from app.services.beauty_lexicon import BEAUTY_LEXICON

        assert "效果" not in BEAUTY_LEXICON
        assert "價格" not in BEAUTY_LEXICON

