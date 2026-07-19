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

        assert detail == {"content": "", "published_at": None}
