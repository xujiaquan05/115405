# backend/tests/test_rag_platform_and_comments.py

"""RAG 的兩個實際缺口。

1. 平台：KNOWN_PLATFORMS 只列了 ptt / dcard，後來加入的 Mobile01 與 Threads
   沒補上。使用者問「Mobile01 上怎麼說」時，意圖解析回傳的平台不在清單裡，
   retrieve_articles 的平台條件就整個被跳過，答案混進其他三個平台的文章，
   畫面上也不會有任何提示。

2. 留言：檢索用 ILIKE 搜整個 content，留言接在主文後的「【留言】」段落裡，
   所以留言算數；但壓縮時只取內文前 300 字，留言永遠被截掉。
   結果是「因為某則留言而被選中的文章」，那則留言卻進不了 prompt。
"""

from types import SimpleNamespace

from app.services import rag_service
from app.services.article_compressor import compress_articles_for_llm, split_main_and_comments


def _article(content: str, title: str = "標題", push_count: int = 5):
    return SimpleNamespace(
        title=title,
        content=content,
        push_count=push_count,
        published_at=None,
        url="https://example.com/1",
        board=SimpleNamespace(name="facelift"),
        author=SimpleNamespace(username="someone"),
    )


class TestPlatformDetection:
    def test_every_crawled_platform_can_be_locked_on(self):
        # 有爬蟲的平台就該能被查詢鎖定，否則使用者指定了也沒作用。
        assert rag_service.KNOWN_PLATFORMS == {"ptt", "dcard", "mobile01", "threads"}

    def test_mobile01_is_detected(self):
        intent = rag_service._fallback_intent("Mobile01 上大家怎麼看音波拉皮")

        assert intent["platform"] == "mobile01"

    def test_threads_is_detected(self):
        intent = rag_service._fallback_intent("Threads 上的醫美討論多嗎")

        assert intent["platform"] == "threads"

    def test_dcard_still_works(self):
        assert rag_service._fallback_intent("dcard 有人推薦診所嗎")["platform"] == "dcard"

    def test_no_platform_mentioned_means_all(self):
        assert rag_service._fallback_intent("玻尿酸的評價如何")["platform"] == "all"

    def test_fragile_skin_is_not_mistaken_for_threads(self):
        # 「脆弱」在醫美討論裡很常見，不能因此把問題當成只問 Threads。
        assert rag_service._fallback_intent("脆弱肌膚適合雷射嗎")["platform"] == "all"


class TestSplitMainAndComments:
    def test_splits_at_the_marker(self):
        main_text, comments = split_main_and_comments("主文內容\n【留言】\n- 推薦\n- 不推")

        assert main_text == "主文內容"
        assert comments == "- 推薦\n- 不推"

    def test_article_without_comments(self):
        assert split_main_and_comments("只有主文") == ("只有主文", "")


class TestCommentsReachThePrompt:
    def test_comments_survive_even_when_the_main_post_fills_its_budget(self):
        article = _article("主" * 500 + "【留言】" + "這家診所術後照顧很細心")

        context = compress_articles_for_llm(
            [article], max_chars_per_article=300, max_comment_chars=300
        )

        # 主文用滿 300 字的額度，留言仍然要進得去——這正是原本壞掉的地方。
        assert "這家診所術後照顧很細心" in context
        assert "Comments:" in context

    def test_the_comment_marker_does_not_eat_into_the_main_post_budget(self):
        article = _article("主文" + "【留言】" + "留" * 500)

        context = compress_articles_for_llm(
            [article], max_chars_per_article=300, max_comment_chars=50
        )

        assert "Content preview: 主文" in context
        assert context.count("留") == 50  # 留言有自己的上限，不會灌爆 prompt

    def test_no_comment_line_when_there_are_no_comments(self):
        context = compress_articles_for_llm([_article("PTT 文章沒有留言內容")])

        assert "Comments:" not in context
