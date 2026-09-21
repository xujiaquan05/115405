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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.time_utils import taiwan_now
from app.models.database_models import Article
from app.services import embedding_service, rag_service
from app.services.article_service import get_or_create_board, get_or_create_platform
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


class TestSplitIntoChunks:
    def test_a_short_article_is_a_single_chunk(self):
        article = SimpleNamespace(title="音波拉皮心得", content="做完第三天還是很腫")

        chunks = embedding_service.split_into_chunks(article)

        assert len(chunks) == 1
        assert "音波拉皮心得" in chunks[0]
        assert "做完第三天還是很腫" in chunks[0]

    def test_a_long_article_is_split_and_nothing_is_dropped(self):
        # 先前只取前 1000 字，實測有 1,138 篇超過而被截掉，
        # 合計 772,722 字從來沒進過向量。切段就是為了這件事。
        body = "".join(str(index % 10) for index in range(3000))
        article = SimpleNamespace(title="標題", content=body)

        chunks = embedding_service.split_into_chunks(article)

        assert len(chunks) > 1
        # 文章結尾也要出現在某一段裡，不能像以前一樣被丟掉。
        assert any(body[-50:] in chunk for chunk in chunks)

    def test_chunks_overlap_so_a_cut_sentence_survives_on_one_side(self):
        body = "".join(str(index % 10) for index in range(1000))
        article = SimpleNamespace(title="", content=body)

        chunks = embedding_service.split_into_chunks(article)
        tail_of_first = chunks[0][-embedding_service.CHUNK_OVERLAP:]

        assert tail_of_first in chunks[1]

    def test_every_chunk_carries_the_title(self):
        # 從中段切出來的片段常常只剩代名詞，補上標題才知道在講哪個療程。
        article = SimpleNamespace(title="音波拉皮心得", content="內" * 1500)

        chunks = embedding_service.split_into_chunks(article)

        assert len(chunks) > 1
        assert all(chunk.startswith("音波拉皮心得") for chunk in chunks)

    def test_comments_are_chunked_too(self):
        # 單一向量時留言被排除（會稀釋主題）；切段後每則留言自成一段。
        article = SimpleNamespace(
            title="標題",
            content="主文" * 200 + "\n【留言】\n- 這家診所術後照顧很細心",
        )

        chunks = embedding_service.split_into_chunks(article)

        assert any("這家診所術後照顧很細心" in chunk for chunk in chunks)

    def test_a_very_long_article_is_capped(self):
        article = SimpleNamespace(title="標題", content="內" * 100_000)

        chunks = embedding_service.split_into_chunks(article)

        assert len(chunks) == embedding_service.MAX_CHUNKS_PER_ARTICLE

    def test_an_empty_article_produces_nothing_to_embed(self):
        assert embedding_service.split_into_chunks(
            SimpleNamespace(title="", content="")
        ) == []


class TestRankBySimilarity:
    """餘弦相似度排序。用假的 embed_texts，不呼叫真正的 API。"""

    def _db_returning(self, rows):
        return SimpleNamespace(execute=lambda _statement: SimpleNamespace(all=lambda: rows))

    def test_orders_by_closeness_to_the_question(self, monkeypatch):
        # 每列是 (article_id, 段落原文, 向量)。
        rows = [
            (1, "段落一", pack_vector([1.0, 1.0])),
            (2, "段落二", pack_vector([1.0, 0.0])),
            (3, "段落三", pack_vector([-1.0, 0.0])),
        ]
        monkeypatch.setattr(embedding_service, "embed_texts", lambda _texts, task_type: [[1.0, 0.0]])

        ranked = embedding_service.rank_by_similarity(
            self._db_returning(rows), "問題", [1, 2, 3]
        )

        assert [article_id for article_id, _score, _chunk in ranked] == [2, 1, 3]
        assert ranked[0][1] == pytest.approx(1.0)
        assert ranked[0][2] == "段落二"
        assert ranked[-1][1] == pytest.approx(-1.0)

    def test_an_article_is_scored_by_its_best_chunk_not_its_average(self, monkeypatch):
        # 一篇長文：只有第二段真的回答了問題，其他段落離題。
        # 取平均的話這篇會被離題的段落拉低而埋掉。
        rows = [
            (1, "離題的開場", pack_vector([-1.0, 0.0])),
            (1, "正好回答問題的那一段", pack_vector([1.0, 0.0])),
            (2, "普通相關", pack_vector([0.7, 0.7])),
        ]
        monkeypatch.setattr(embedding_service, "embed_texts", lambda _texts, task_type: [[1.0, 0.0]])

        ranked = embedding_service.rank_by_similarity(self._db_returning(rows), "問題", [1, 2])

        assert ranked[0][0] == 1
        assert ranked[0][1] == pytest.approx(1.0)
        # 而且要回報是哪一段命中，組 prompt 時才送得出去。
        assert ranked[0][2] == "正好回答問題的那一段"

        # 同一篇只出現一次，不會因為多段而洗版。
        assert [article_id for article_id, _score, _chunk in ranked] == [1, 2]

    def test_no_candidates_means_no_work(self, monkeypatch):
        def fail(*_args, **_kwargs):
            raise AssertionError("不該為了空候選去呼叫 API")

        monkeypatch.setattr(embedding_service, "embed_texts", fail)

        assert embedding_service.rank_by_similarity(self._db_returning([]), "問題", []) == []

    def test_an_embedding_failure_falls_back_to_no_vector_results(self, monkeypatch):
        rows = [(1, "段落", pack_vector([1.0, 0.0]))]

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


class TestKeywordRanking:
    """關鍵字檢索要先比命中程度，再比熱度。

    實測到的問題：問「音波拉皮術後多久才會消腫」時，排第一的是一篇
    購物分享文「跟風脆爆買的單品好物推推」——三個關鍵字只命中「消腫」，
    而且是內文第 141 個字，但它有 217 推。當時排序只看 push_count，
    於是它壓過了整篇都在講音波術後消腫的文章，還被 RRF 帶進合併結果的前段。
    """

    @pytest.fixture
    def db_session(self):
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        yield session
        session.close()

    def _add(self, db, title, content, push_count):
        platform = get_or_create_platform(db, "ptt")
        board = get_or_create_board(db, platform.id, "facelift")
        article = Article(
            unique_id=f"u{title}",
            platform_id=platform.id,
            board_id=board.id,
            title=title,
            content=content,
            push_count=push_count,
            published_at=taiwan_now(),
        )
        db.add(article)
        db.commit()
        return article

    def _intent(self, keywords):
        return {
            "keywords": keywords,
            "sentiment": "all",
            "days": 30,
            "question_type": "opinion",
            "platform": "all",
        }

    def test_a_popular_incidental_match_loses_to_an_on_topic_article(self, db_session):
        self._add(db_session, "跟風爆買的單品好物推推", "買了一堆東西，其中有消腫的產品", 217)
        self._add(db_session, "音波拉皮術後消腫紀錄", "音波拉皮做完的術後消腫過程", 2)

        results = rag_service.retrieve_by_keyword(
            db_session, self._intent(["音波拉皮", "術後", "消腫"])
        )

        assert results[0].title == "音波拉皮術後消腫紀錄"

    def test_a_title_match_outranks_a_content_only_match(self, db_session):
        self._add(db_session, "隨手記錄", "文章中間提到玻尿酸一次", 500)
        self._add(db_session, "玻尿酸心得", "分享一些感想", 1)

        results = rag_service.retrieve_by_keyword(db_session, self._intent(["玻尿酸"]))

        assert results[0].title == "玻尿酸心得"

    def test_popularity_still_decides_between_equally_matching_articles(self, db_session):
        # 熱度沒有被廢掉，只是退到第二順位：
        # 這是輿情系統，200 推的抱怨本來就比 2 推的更該被看見。
        self._add(db_session, "玻尿酸心得 A", "玻尿酸", 5)
        self._add(db_session, "玻尿酸心得 B", "玻尿酸", 300)

        results = rag_service.retrieve_by_keyword(db_session, self._intent(["玻尿酸"]))

        assert results[0].title == "玻尿酸心得 B"

    def test_matching_more_keywords_ranks_higher(self, db_session):
        self._add(db_session, "只提音波", "音波", 100)
        self._add(db_session, "音波與術後", "音波 術後都有講", 1)

        results = rag_service.retrieve_by_keyword(db_session, self._intent(["音波", "術後"]))

        assert results[0].title == "音波與術後"


class TestPendingExcludesUnembeddableArticles:
    """空白文章不能永遠留在待處理清單裡。

    實測：補跑腳本跑到 100% 之後仍然停不下來，連續三輪回報
    「待處理數量沒有減少，可能是額度用完」才被守門機制擋下。
    追下去是資料庫裡有一篇 id=3127 的文章，標題與內文都是空字串——
    每輪都被選中、每輪都切不出段落，數量自然一篇也沒少。
    額度其實完全沒問題，警告訊息是誤導。
    """

    @pytest.fixture
    def db_session(self):
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        yield session
        session.close()

    def _add(self, db, title, content):
        platform = get_or_create_platform(db, "ptt")
        board = get_or_create_board(db, platform.id, "facelift")
        article = Article(
            unique_id=f"u{title}{content}",
            platform_id=platform.id,
            board_id=board.id,
            title=title,
            content=content,
            push_count=0,
            published_at=taiwan_now(),
        )
        db.add(article)
        db.commit()
        return article

    def test_an_article_with_no_text_is_not_pending(self, db_session):
        self._add(db_session, "", "")

        assert embedding_service.count_pending_embeddings(db_session) == 0

    def test_an_article_with_only_a_title_is_still_pending(self, db_session):
        # 標題就足以切出一段，這種文章該被處理。
        self._add(db_session, "只有標題的文章", "")

        assert embedding_service.count_pending_embeddings(db_session) == 1

    def test_the_count_matches_what_will_actually_be_processed(self, db_session):
        # 兩邊條件對不上，就會出現「還有待處理卻永遠處理不掉」的空轉。
        self._add(db_session, "", "")
        self._add(db_session, "正常文章", "有內容")

        pending = embedding_service.count_pending_embeddings(db_session)
        selected = embedding_service._pending_articles(db_session, max_articles=100)

        assert pending == len(selected) == 1
