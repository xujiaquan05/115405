# backend/tests/test_vector_search.py

"""語意檢索（向量）與混合排名。

為什麼要加向量檢索？
原本只有 SQL 的 ILIKE：問「打完填充物臉會腫嗎」，
只有真的寫了「填充物」三個字的文章找得到，
寫「玻尿酸」「微整針劑」的一篇都撈不到——講的是同一件事卻漏掉。

但向量也不是萬靈丹：專有名詞（診所名、品牌名）反而是字面比對更可靠。
所以兩種檢索都跑，再用 Reciprocal Rank Fusion 合併。
"""

import struct
from types import SimpleNamespace

import pytest

from app.services import embedding_service, rag_service
from app.services.embedding_service import pack_vector, unpack_vector


def _article(article_id: int):
    return SimpleNamespace(id=article_id, title=f"文章 {article_id}")


def _article_by_id(articles, article_id: int):
    return next(article for article in articles if article.id == article_id)


class TestVectorPacking:
    def test_round_trip(self):
        values = [0.5, -0.25, 0.125]

        assert unpack_vector(pack_vector(values)) == values

    def test_packs_as_float32(self):
        # 一維 4 bytes：768 維就是 3KB，全庫近萬篇約 30MB。
        assert len(pack_vector([1.0] * 768)) == 768 * 4

    def test_layout_matches_what_numpy_reads_back(self):
        # rank_by_similarity 是用 np.frombuffer 直接讀這些位元組，
        # 位元組順序錯了不會報錯，只會安靜地算出垃圾相似度。
        raw = pack_vector([1.5, 2.5])

        assert struct.unpack("<2f", raw) == (1.5, 2.5)


class TestTextForEmbedding:
    def test_uses_title_and_main_post_without_comments(self):
        article = SimpleNamespace(
            title="音波拉皮心得",
            content="做完第三天還是很腫\n【留言】\n- 我也是\n- 推薦這家",
        )

        text = embedding_service.text_for_embedding(article)

        assert "音波拉皮心得" in text
        assert "做完第三天還是很腫" in text
        # 留言是別人的意見；混進來向量會變成「整串討論的平均」。
        assert "推薦這家" not in text

    def test_truncates_long_content(self):
        article = SimpleNamespace(title="標題", content="內" * 5000)

        assert len(embedding_service.text_for_embedding(article)) <= (
            embedding_service.MAX_EMBED_CHARS
        )


class TestRankBySimilarity:
    """餘弦相似度排序。用假的 embed_texts，不呼叫真正的 API。"""

    def _db_returning(self, rows):
        return SimpleNamespace(execute=lambda _statement: SimpleNamespace(all=lambda: rows))

    def test_orders_by_closeness_to_the_question(self, monkeypatch):
        # 三篇文章的向量：第 2 篇與問題同方向，第 3 篇相反。
        rows = [
            (1, pack_vector([1.0, 1.0])),
            (2, pack_vector([1.0, 0.0])),
            (3, pack_vector([-1.0, 0.0])),
        ]
        monkeypatch.setattr(embedding_service, "embed_texts", lambda _texts, task_type: [[1.0, 0.0]])

        ranked = embedding_service.rank_by_similarity(
            self._db_returning(rows), "問題", [1, 2, 3]
        )

        assert [article_id for article_id, _score in ranked] == [2, 1, 3]
        assert ranked[0][1] == pytest.approx(1.0)
        assert ranked[-1][1] == pytest.approx(-1.0)

    def test_no_candidates_means_no_work(self, monkeypatch):
        def fail(*_args, **_kwargs):
            raise AssertionError("不該為了空候選去呼叫 API")

        monkeypatch.setattr(embedding_service, "embed_texts", fail)

        assert embedding_service.rank_by_similarity(self._db_returning([]), "問題", []) == []

    def test_an_embedding_failure_falls_back_to_no_vector_results(self, monkeypatch):
        rows = [(1, pack_vector([1.0, 0.0]))]

        def boom(*_args, **_kwargs):
            raise RuntimeError("API down")

        monkeypatch.setattr(embedding_service, "embed_texts", boom)

        # 向量掛掉不該讓整個問答失敗，關鍵字檢索仍要能回答。
        assert embedding_service.rank_by_similarity(self._db_returning(rows), "問題", [1]) == []


class TestFuseRankings:
    def test_appearing_in_both_rankings_beats_being_first_in_only_one(self):
        keyword = [_article(1), _article(2), _article(3)]
        vector = [_article(2), _article(3), _article(4)]

        fused = rag_service.fuse_rankings([keyword, vector])

        # 1 是關鍵字第一名但向量沒找到；2 在兩邊分別是第二與第一。
        # K=60 把名次之間的差距壓得很小，所以「兩邊都上榜」會贏。
        assert fused[0].id == 2
        assert fused.index(_article_by_id(fused, 1)) > 0

    def test_one_top_hit_can_outweigh_two_middling_ones(self):
        # 提醒後人：分數不是「上榜次數」。1/63 + 1/61 > 1/62 + 1/62，
        # 所以「一邊第三、一邊第一」會些微贏過「兩邊都第二」。
        keyword = [_article(1), _article(2), _article(3)]
        vector = [_article(3), _article(2), _article(4)]

        assert rag_service.fuse_rankings([keyword, vector])[0].id == 3

    def test_articles_found_by_only_one_method_are_still_included(self):
        fused = rag_service.fuse_rankings([[_article(1)], [_article(2)]])

        assert {article.id for article in fused} == {1, 2}

    def test_respects_the_limit(self):
        ranking = [_article(index) for index in range(10)]

        assert len(rag_service.fuse_rankings([ranking], limit=3)) == 3

    def test_no_duplicates_when_both_rankings_share_articles(self):
        fused = rag_service.fuse_rankings([[_article(1), _article(2)], [_article(2), _article(1)]])

        assert [article.id for article in fused] == [1, 2]


class TestRetrieveArticlesFallback:
    """向量還沒補完、或問題文字缺席時，要能安靜退回關鍵字檢索。"""

    def test_without_a_question_it_stays_keyword_only(self, monkeypatch):
        monkeypatch.setattr(rag_service, "retrieve_by_keyword", lambda *_a, **_k: [_article(1)])

        def fail(*_args, **_kwargs):
            raise AssertionError("沒有問題文字時不該做語意檢索")

        monkeypatch.setattr(rag_service, "retrieve_by_vector", fail)

        assert rag_service.retrieve_articles(db=None, intent={}) == [_article(1)]

    def test_empty_vector_results_do_not_wipe_out_the_keyword_results(self, monkeypatch):
        monkeypatch.setattr(rag_service, "retrieve_by_keyword", lambda *_a, **_k: [_article(1)])
        monkeypatch.setattr(rag_service, "retrieve_by_vector", lambda *_a, **_k: [])

        result = rag_service.retrieve_articles(db=None, intent={}, question="問題")

        assert [article.id for article in result] == [1]
