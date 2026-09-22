# backend/tests/test_ptt_crawler.py

from datetime import datetime

import pytest

from app.crawlers.ptt_crawler import PTTCrawler


@pytest.fixture
def crawler():
    return PTTCrawler()


class TestParsePushCount:
    def test_normal_number(self, crawler):
        assert crawler._parse_push_count("15") == 15

    def test_explosive(self, crawler):
        assert crawler._parse_push_count("爆") == 100

    def test_negative(self, crawler):
        assert crawler._parse_push_count("X2") == -2

    def test_empty(self, crawler):
        assert crawler._parse_push_count("") == 0
        assert crawler._parse_push_count("   ") == 0

    def test_garbage(self, crawler):
        assert crawler._parse_push_count("abc") == 0
        assert crawler._parse_push_count("Xabc") == 0


class TestParsePttTime:
    def test_valid_time(self, crawler):
        parsed = crawler._parse_ptt_time("Mon Jan  5 12:00:00 2026")
        assert parsed == datetime(2026, 1, 5, 12, 0, 0)

    def test_invalid_time(self, crawler):
        assert crawler._parse_ptt_time("not a time") is None
        assert crawler._parse_ptt_time("") is None


class TestUniqueId:
    def test_same_input_same_id(self, crawler):
        first = crawler._generate_unique_id("ptt", "facelift", "http://x/1")
        second = crawler._generate_unique_id("ptt", "facelift", "http://x/1")
        assert first == second

    def test_different_url_different_id(self, crawler):
        first = crawler._generate_unique_id("ptt", "facelift", "http://x/1")
        second = crawler._generate_unique_id("ptt", "facelift", "http://x/2")
        assert first != second


class TestJunkTitleFilter:
    def test_announcement_titles_are_junk(self, crawler):
        assert crawler._is_junk_title("[公告] 板規 v3.0")
        assert crawler._is_junk_title("Fw: [公告] 全站活動")
        assert crawler._is_junk_title("[水桶] 違規名單 2026-07")
        assert crawler._is_junk_title("[置底] 閒聊文")

    def test_normal_titles_are_kept(self, crawler):
        assert not crawler._is_junk_title("[心得] 玻尿酸術後一個月分享")
        assert not crawler._is_junk_title("[問題] 皮秒雷射恢復期")
        assert not crawler._is_junk_title("[討論] 診所報價差很多正常嗎")


LIST_HTML = """
<html><body>
<div class="r-ent">
  <div class="nrec">10</div>
  <div class="title"><a href="/bbs/facelift/M.1.A.001.html">[心得] 音波拉提心得</a></div>
  <div class="author">alice</div>
</div>
<div class="r-ent">
  <div class="nrec"></div>
  <div class="title"><a href="/bbs/facelift/M.2.A.002.html">[公告] 板規與發文規範</a></div>
  <div class="author">mod</div>
</div>
<div class="r-ent">
  <div class="nrec">爆</div>
  <div class="title"><a href="/bbs/facelift/M.3.A.003.html">[問題] 雷射除斑價格</a></div>
  <div class="author">bob</div>
</div>
</body></html>
"""


class TestParseArticleList:
    def test_junk_articles_excluded_from_list(self, crawler, monkeypatch):
        monkeypatch.setattr(crawler, "_safe_get", lambda url: LIST_HTML)

        articles = crawler.parse_article_list("facelift", "http://fake-url")

        titles = [article["title"] for article in articles]
        assert len(articles) == 2
        assert "[心得] 音波拉提心得" in titles
        assert "[問題] 雷射除斑價格" in titles
        assert all("公告" not in title for title in titles)

    def test_push_counts_parsed(self, crawler, monkeypatch):
        monkeypatch.setattr(crawler, "_safe_get", lambda url: LIST_HTML)

        articles = crawler.parse_article_list("facelift", "http://fake-url")

        push_by_title = {a["title"]: a["push_count"] for a in articles}
        assert push_by_title["[心得] 音波拉提心得"] == 10
        assert push_by_title["[問題] 雷射除斑價格"] == 100


ARTICLE_HTML = """
<html><body>
<div id="main-content">
<div class="article-metaline"><span class="article-meta-tag">作者</span><span class="article-meta-value">tester</span></div>
<div class="article-metaline"><span class="article-meta-tag">看板</span><span class="article-meta-value">facelift</span></div>
<div class="article-metaline"><span class="article-meta-tag">標題</span><span class="article-meta-value">[心得] 測試</span></div>
<div class="article-metaline"><span class="article-meta-tag">時間</span><span class="article-meta-value">Mon Jan  5 12:00:00 2026</span></div>
分享一下 https://example.com/a--b 這個連結
真的很有用
--
我的簽名檔
※ 發信站: 批踢踢實業坊(ptt.cc)
<div class="push">推 someone: 推文內容</div>
</div>
</body></html>
"""


class TestParseArticleDetail:
    def test_signature_removed_but_inline_dashes_kept(self, crawler, monkeypatch):
        # 舊 bug：content.split("--")[0] 會在 URL 內的 "--" 處
        # 把文章截斷。現在只會在獨立的 "--" 行切開。
        monkeypatch.setattr(crawler, "_safe_get", lambda url: ARTICLE_HTML)

        detail = crawler.parse_article_detail("http://fake-url")

        assert "https://example.com/a--b" in detail["content"]
        assert "真的很有用" in detail["content"]
        assert "簽名檔" not in detail["content"]
        assert "發信站" not in detail["content"]
        assert "推文內容" not in detail["content"]

    def test_published_at_parsed_from_meta(self, crawler, monkeypatch):
        monkeypatch.setattr(crawler, "_safe_get", lambda url: ARTICLE_HTML)

        detail = crawler.parse_article_detail("http://fake-url")

        assert detail["published_at"] == datetime(2026, 1, 5, 12, 0, 0)

    def test_fetch_failure_returns_empty(self, crawler, monkeypatch):
        monkeypatch.setattr(crawler, "_safe_get", lambda url: None)

        detail = crawler.parse_article_detail("http://fake-url")

        assert detail == {"content": "", "published_at": None, "comments": []}


# 依實際 PTT 文章頁結構撰寫的樣本（meta 四行 + 正文 + 三則推文 + 簽名檔）。
DETAIL_HTML = """
<div id="main-content">
  <div class="article-metaline"><span class="article-meta-tag">作者</span><span class="article-meta-value">someone (阿明)</span></div>
  <div class="article-metaline-right"><span class="article-meta-tag">看板</span><span class="article-meta-value">facelift</span></div>
  <div class="article-metaline"><span class="article-meta-tag">標題</span><span class="article-meta-value">[心得] 音波拉皮三個月</span></div>
  <div class="article-metaline"><span class="article-meta-tag">時間</span><span class="article-meta-value">Mon Jan  1 12:00:00 2024</span></div>
  做完三個月了，線條有回來一些。
--
  <span class="f2">※ 發信站: 批踢踢實業坊</span>
  <div class="push"><span class="hl push-tag">推 </span><span class="f3 hl push-userid">aaa</span><span class="f3 push-content">: 我也做過，效果不錯</span><span class="push-ipdatetime"> 01/01 12:01</span></div>
  <div class="push"><span class="hl push-tag">噓 </span><span class="f3 hl push-userid">bbb</span><span class="f3 push-content">: 我覺得根本沒用，浪費錢</span><span class="push-ipdatetime"> 01/01 12:02</span></div>
  <div class="push"><span class="hl push-tag">→ </span><span class="f3 hl push-userid">ccc</span><span class="f3 push-content">: 請問是哪一家診所</span><span class="push-ipdatetime"> 01/01 12:03</span></div>
  <div class="push"><span class="hl push-tag">推 </span><span class="f3 hl push-userid">ddd</span><span class="f3 push-content">:   </span><span class="push-ipdatetime"> 01/01 12:04</span></div>
</div>
"""


class TestParsePushes:
    """PTT 推文是這個站台最有價值的輿情來源，先前整段被丟掉。

    實測：資料庫裡 9,272 篇 PTT 文章有 0 則留言，
    而 Dcard 332 篇就有 1,107 則。原因是 parse_article_detail
    直接 decompose 掉 div.push，只留下列表頁的推文「數字」。
    """

    def _main_content(self):
        from bs4 import BeautifulSoup

        return BeautifulSoup(DETAIL_HTML, "html.parser").select_one("#main-content")

    def test_collects_pushes_with_their_tag(self, crawler):
        pushes = crawler.parse_pushes(self._main_content())

        # 推 / 噓 本身就是最直接的情緒表態，不能丟。
        assert pushes[0] == "推 我也做過，效果不錯"
        assert pushes[1] == "噓 我覺得根本沒用，浪費錢"
        assert pushes[2] == "→ 請問是哪一家診所"

    def test_skips_empty_pushes(self, crawler):
        # 只有標籤沒有內容的推文（PTT 上常見）不該變成一則空留言。
        assert len(crawler.parse_pushes(self._main_content())) == 3

    def test_does_not_keep_the_userid(self, crawler):
        # 使用者代號對輿情分析沒有幫助，而且是個人資料。
        pushes = crawler.parse_pushes(self._main_content())

        assert all("aaa" not in push and "bbb" not in push for push in pushes)

    def test_respects_the_cap(self):
        limited = PTTCrawler(max_pushes=2)

        assert len(limited.parse_pushes(self._main_content())) == 2

    def test_can_be_turned_off(self):
        assert PTTCrawler(fetch_pushes=False).parse_pushes(self._main_content()) == []


class TestMergeContentAndComments:
    def test_uses_the_same_marker_as_the_other_platforms(self, crawler):
        merged = crawler.merge_content_and_comments("主文", ["推 好", "噓 不好"])

        # 下游的情緒評分、關鍵字分析與向量切段都是靠這個標記切主文與留言，
        # 格式跟 Dcard / Mobile01 / Threads 不一致的話就得分平台處理。
        assert merged == "主文\n【留言】\n- 推 好\n- 噓 不好"

    def test_an_article_without_pushes_is_unchanged(self, crawler):
        assert crawler.merge_content_and_comments("只有主文", []) == "只有主文"

    def test_handles_missing_content(self, crawler):
        assert crawler.merge_content_and_comments(None, []) == ""
