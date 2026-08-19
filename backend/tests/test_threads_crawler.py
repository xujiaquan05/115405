# backend/tests/test_threads_crawler.py

from datetime import datetime

import pytest

from app.crawlers.threads_crawler import ThreadsCrawler


@pytest.fixture
def crawler():
    return ThreadsCrawler()


# 依實際 Threads 搜尋結果區塊擷取到的文字撰寫。
RAW_WITH_TAG = "keepunder25\n醫美\n10小時\n台北市有哪些醫美診所有生日優惠活動嗎？\n下半年想打電波、音波、肉毒。\n翻譯\n5\n12\n1"
RAW_SIMPLE = "ting_ting817\n9小時\n有推薦的醫美診所嗎\n翻譯\n5\n29"


class TestSplitTextAndCounts:
    def test_removes_username_tag_and_relative_time(self):
        content, count = ThreadsCrawler._split_text_and_counts(
            RAW_WITH_TAG, username="keepunder25", keyword="醫美"
        )
        assert content == "台北市有哪些醫美診所有生日優惠活動嗎？\n下半年想打電波、音波、肉毒。"
        assert count == 12  # 讚 / 回覆 / 轉發取最大值

    def test_simple_post(self):
        content, count = ThreadsCrawler._split_text_and_counts(RAW_SIMPLE, username="ting_ting817")
        assert content == "有推薦的醫美診所嗎"
        assert count == 29

    def test_counts_without_translate_line(self):
        content, count = ThreadsCrawler._split_text_and_counts("user\n3天\n很棒的診所\n8\n3", username="user")
        assert content == "很棒的診所"
        assert count == 8

    def test_empty(self):
        assert ThreadsCrawler._split_text_and_counts(None) == ("", 0)
        assert ThreadsCrawler._split_text_and_counts("") == ("", 0)


class TestToArticle:
    def test_maps_fields(self, crawler):
        post = {
            "url": "/@keepunder25/post/DcNbr6ZkzR4",
            "user": "keepunder25",
            "datetime": "2026-08-19T05:25:47.000Z",
            "raw_text": RAW_WITH_TAG,
        }
        art = crawler._to_article(post, "醫美")

        assert art["platform_name"] == "threads"
        assert art["board_name"] == "醫美"          # 看板存搜尋關鍵字
        assert art["author_username"] == "keepunder25"
        assert art["url"] == "https://www.threads.com/@keepunder25/post/DcNbr6ZkzR4"
        assert art["title"] == "台北市有哪些醫美診所有生日優惠活動嗎？"  # 取內文第一行，不是標籤
        assert art["push_count"] == 12
        assert art["published_at"] == datetime(2026, 8, 19, 5, 25, 47)

    def test_unique_id_ignores_keyword(self, crawler):
        # 同一篇貼文可能同時符合多個關鍵字，unique_id 必須相同以免重複收錄。
        post = {"url": "/@u/post/X1", "user": "u", "datetime": None, "raw_text": "u\n1小時\n打肉毒心得"}
        assert crawler._to_article(post, "醫美")["unique_id"] == crawler._to_article(post, "保養")["unique_id"]

    def test_unique_id_differs_by_post(self, crawler):
        a = crawler._to_article({"url": "/@u/post/X1", "user": "u", "raw_text": "x"}, "醫美")
        b = crawler._to_article({"url": "/@u/post/X2", "user": "u", "raw_text": "x"}, "醫美")
        assert a["unique_id"] != b["unique_id"]


class TestParseDt:
    def test_iso_with_z(self):
        assert ThreadsCrawler._parse_dt("2026-08-19T06:35:40.000Z") == datetime(2026, 8, 19, 6, 35, 40)

    def test_invalid(self):
        assert ThreadsCrawler._parse_dt("nope") is None
        assert ThreadsCrawler._parse_dt(None) is None
