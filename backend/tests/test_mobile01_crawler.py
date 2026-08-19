# backend/tests/test_mobile01_crawler.py

from datetime import datetime

import pytest

from app.crawlers.mobile01_crawler import Mobile01Crawler


@pytest.fixture
def crawler():
    return Mobile01Crawler()


# 依實際 Mobile01 列表頁結構撰寫的樣本（標題列 + 兩篇文章 + 一列廣告）。
LIST_HTML = """
<div class="l-listTable">
  <div class="l-listTable__tr">
    <div class="l-listTable__td">主題</div>
    <div class="l-listTable__td l-listTable__td--count"><div class="o-fMini">回覆</div></div>
  </div>
  <div class="l-listTable__tr">
    <div class="l-listTable__td">
      <div class="c-listTableTd"><div class="c-listTableTd__title">
        <a class="c-link u-ellipsis" href="topicdetail.php?f=371&amp;t=7291695">認真保養這麼多年，你最後悔花錢買過什麼？</a>
      </div></div>
    </div>
    <div class="l-listTable__td l-listTable__td--time">
      <div><a class="c-link u-ellipsis u-username" href="#">wei1023567</a></div>
      <div class="o-fNotes">2026-08-17 16:43</div>
    </div>
    <div class="l-listTable__td l-listTable__td--time">
      <div><a class="c-link u-ellipsis u-username" href="#">ColdsummerX</a></div>
      <div class="o-fNotes">2026-08-19 22:28</div>
    </div>
    <div class="l-listTable__td l-listTable__td--count"><div class="o-fMini">7</div></div>
  </div>
  <div class="l-listTable__tr">
    <div class="l-listTable__td">
      <div class="c-listTableTd__title">
        <a class="c-link u-ellipsis" href="topicdetail.php?f=371&amp;t=7288888">請益 雷射術後保養推薦</a>
      </div>
    </div>
    <div class="l-listTable__td l-listTable__td--time">
      <div><a class="c-link u-ellipsis u-username" href="#">beautyfan</a></div>
      <div class="o-fNotes">2026-08-10 09:05</div>
    </div>
    <div class="l-listTable__td l-listTable__td--count"><div class="o-fMini">1,234</div></div>
  </div>
  <div class="l-listTable__tr">
    <div class="l-listTable__td"><span>贊助商廣告</span></div>
  </div>
</div>
"""

DETAIL_HTML = """
<div>
  <h1>認真保養這麼多年，你最後悔花錢買過什麼？</h1>
  <article>  前幾天整理房間丟掉一堆過期保養品  \n\n\n  覺得花了好多冤枉錢  </article>
  <article>最後悔的是為了滿額折扣亂囤貨</article>
  <article>我也是，精華液買太多用不完</article>
  <article>   </article>
</div>
"""


class TestParseTopicList:
    def test_extracts_articles_and_skips_header_and_ads(self, crawler):
        topics = crawler.parse_topic_list(LIST_HTML, "371")
        assert len(topics) == 2

        first = topics[0]
        assert first["platform_name"] == "mobile01"
        assert first["board_name"] == "371"
        assert first["title"] == "認真保養這麼多年，你最後悔花錢買過什麼？"
        assert first["author_username"] == "wei1023567"  # 取原發表者，不是最後回覆者
        assert first["url"] == "https://www.mobile01.com/topicdetail.php?f=371&t=7291695"
        assert first["push_count"] == 7
        assert first["published_at"] == datetime(2026, 8, 17, 16, 43)
        assert first["unique_id"]

    def test_reply_count_parsed(self, crawler):
        topics = crawler.parse_topic_list(LIST_HTML, "371")
        assert topics[1]["push_count"] == 1234  # 千分位逗號要能解析

    def test_empty_html_returns_empty(self, crawler):
        assert crawler.parse_topic_list("<div></div>", "371") == []


class TestParseTopicDetail:
    def test_main_post_and_replies(self, crawler):
        content, replies = crawler.parse_topic_detail(DETAIL_HTML)

        assert "前幾天整理房間丟掉一堆過期保養品" in content
        assert "冤枉錢" in content
        assert replies == ["最後悔的是為了滿額折扣亂囤貨", "我也是，精華液買太多用不完"]  # 空白 article 被略過

    def test_replies_can_be_disabled(self):
        crawler = Mobile01Crawler(fetch_replies=False)
        content, replies = crawler.parse_topic_detail(DETAIL_HTML)

        assert content
        assert replies == []

    def test_reply_limit(self):
        crawler = Mobile01Crawler(max_replies=1)
        _content, replies = crawler.parse_topic_detail(DETAIL_HTML)

        assert len(replies) == 1

    def test_no_article_tag(self, crawler):
        assert crawler.parse_topic_detail("<div>沒有內容</div>") == ("", [])


class TestHelpers:
    def test_parse_dt(self):
        assert Mobile01Crawler._parse_dt("wei1023567 2026-08-17 16:43") == datetime(2026, 8, 17, 16, 43)
        assert Mobile01Crawler._parse_dt("no date here") is None
        assert Mobile01Crawler._parse_dt(None) is None

    def test_parse_reply_count(self):
        assert Mobile01Crawler._parse_reply_count("7") == 7
        assert Mobile01Crawler._parse_reply_count("1,234") == 1234
        assert Mobile01Crawler._parse_reply_count("") == 0
        assert Mobile01Crawler._parse_reply_count(None) == 0

    def test_merge_content_and_replies(self):
        merged = Mobile01Crawler._merge_content_and_replies("主文", ["回覆A", "回覆B"])
        assert merged == "主文\n【留言】\n- 回覆A\n- 回覆B"
        assert Mobile01Crawler._merge_content_and_replies("只有主文", []) == "只有主文"
        assert Mobile01Crawler._merge_content_and_replies(None, []) == ""

    def test_unique_id_is_stable_and_url_specific(self, crawler):
        a = crawler._generate_unique_id("mobile01", "371", "http://x/1")
        b = crawler._generate_unique_id("mobile01", "371", "http://x/1")
        c = crawler._generate_unique_id("mobile01", "371", "http://x/2")
        assert a == b and a != c
