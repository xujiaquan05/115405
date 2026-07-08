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
