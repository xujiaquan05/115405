# backend/tests/test_keyword_relevance.py

"""關鍵字檢索的三道把關：丟掉死詞、依稀有度加權、濾掉勉強沾邊的文章。

三者都不花任何 API 額度，全部在 SQL 與 Python 裡完成。

實測到的問題：
問「音波拉皮術後多久才會消腫」時，前 12 篇全部並列 4 分——
隆乳術後、雙眼皮術後、近視鐳射術後跟正確答案不分高下。
追下去發現意圖解析生出的「音波拉皮」在 9,852 篇裡只命中 1 篇
（大家寫的是「音波」），「療程推薦」更是命中 0 篇，
於是排序實際上由「術後」（257 篇）一個詞決定。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.time_utils import taiwan_now
from app.models.database_models import Article
from app.services import rag_service
from app.services.article_service import get_or_create_board, get_or_create_platform


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def add(db, title, content="", push_count=0):
    platform = get_or_create_platform(db, "ptt")
    board = get_or_create_board(db, platform.id, "facelift")
    article = Article(
        unique_id=f"u{title}{content}",
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


def intent_for(keywords):
    return {
        "keywords": keywords,
        "sentiment": "all",
        "days": 30,
        "question_type": "opinion",
        "platform": "all",
    }


class TestKeywordDocumentCounts:
    def test_counts_each_keyword_within_the_candidates(self, db):
        add(db, "音波拉皮分享", "音波拉皮術後心得")
        add(db, "隆乳術後", "術後恢復")
        add(db, "雙眼皮術後", "術後照顧")

        counts = rag_service.keyword_document_counts(db, intent_for(["音波拉皮", "術後"]))

        assert counts == {"音波拉皮": 1, "術後": 3}

    def test_no_keywords_needs_no_query(self, db):
        assert rag_service.keyword_document_counts(db, intent_for([])) == {}


class TestDropDeadKeywords:
    def test_a_keyword_matching_nothing_is_dropped(self):
        intent = intent_for(["拉提", "療程推薦"])

        refined = rag_service.drop_dead_keywords(intent, {"拉提": 28, "療程推薦": 0})

        assert refined["keywords"] == ["拉提"]

    def test_everything_else_in_the_intent_survives(self):
        intent = intent_for(["拉提", "療程推薦"])
        intent["days"] = 90

        refined = rag_service.drop_dead_keywords(intent, {"拉提": 28, "療程推薦": 0})

        assert refined["days"] == 90
        assert refined["platform"] == "all"

    def test_all_keywords_dead_keeps_them(self):
        # 全部落空時檢索本來就找不到東西。刪光的話呼叫端會誤以為
        # 使用者根本沒指定關鍵字，反而回傳一堆不相干的文章。
        intent = intent_for(["療程推薦", "音波拉皮術"])

        refined = rag_service.drop_dead_keywords(intent, {"療程推薦": 0, "音波拉皮術": 0})

        assert refined["keywords"] == ["療程推薦", "音波拉皮術"]


class TestRareTermsOutweighCommonOnes:
    def test_the_rare_keyword_decides_the_order(self, db):
        # 重現實測場景：一個罕見詞（音波拉皮）與一個到處都有的詞（術後）。
        add(db, "音波拉皮分享", "音波拉皮的術後心得")
        for index in range(8):
            add(db, f"隆乳術後 {index}", "術後恢復紀錄", push_count=500)

        results = rag_service.retrieve_by_keyword(db, intent_for(["音波拉皮", "術後"]))

        # 沒有稀有度加權的話，這九篇會並列，再由 push_count 決定，
        # 於是八篇隆乳文會壓過唯一講音波拉皮的那篇。
        assert results[0].title == "音波拉皮分享"

    def test_a_common_term_alone_is_not_enough_to_stay(self, db):
        add(db, "音波拉皮分享", "音波拉皮的術後心得")
        for index in range(8):
            add(db, f"隆乳術後 {index}", "術後恢復紀錄", push_count=500)

        results = rag_service.retrieve_by_keyword(db, intent_for(["音波拉皮", "術後"]))

        # 只沾到常見詞的文章要被門檻擋掉，不該佔滿 prompt。
        assert all("隆乳" not in (article.title or "") for article in results)


class TestScoreFloor:
    def test_an_article_that_only_mentions_the_term_in_passing_is_dropped(self, db):
        # 標題加內文都命中拿 4 份權重，只在內文提過一次拿 1 份，
        # 低於最高分的三分之一，構不上門檻。
        add(db, "玻尿酸心得", "玻尿酸的使用經驗分享")
        add(db, "隨手記錄", "今天順便提到玻尿酸一次")

        results = rag_service.retrieve_by_keyword(db, intent_for(["玻尿酸"]))

        assert [article.title for article in results] == ["玻尿酸心得"]

    def test_matching_a_second_query_term_keeps_an_article_in(self, db):
        # 命中兩個不同的查詢詞是真的證據，不該被門檻誤殺——
        # 即使它在任何單一個詞上都不是最突出的那篇。
        add(db, "拉提療程比較", "拉提的各種療程")
        add(db, "保養品開箱", "談到拉提，也談到鬆弛")

        results = rag_service.retrieve_by_keyword(db, intent_for(["拉提", "鬆弛"]))

        assert "保養品開箱" in [article.title for article in results]

    def test_articles_scoring_alike_are_all_kept(self, db):
        add(db, "拉提心得 A", "拉提")
        add(db, "拉提心得 B", "拉提")

        results = rag_service.retrieve_by_keyword(db, intent_for(["拉提"]))

        assert len(results) == 2

    def test_no_matches_returns_nothing(self, db):
        add(db, "完全無關的文章", "內容也無關")

        assert rag_service.retrieve_by_keyword(db, intent_for(["玻尿酸"])) == []
