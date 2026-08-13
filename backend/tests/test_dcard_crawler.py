# backend/tests/test_dcard_crawler.py

from datetime import datetime

import pytest

from app.crawlers.dcard_crawler import DcardCrawler


@pytest.fixture
def crawler():
    return DcardCrawler()


# 一份模擬 Dcard globalPaging/page 回應（含重複 id 用來驗證去重）。
SAMPLE_BODIES = [
    {
        "widgets": [
            {
                "forumList": {
                    "items": [
                        {"post": {
                            "id": 1001,
                            "title": "玻尿酸心得分享",
                            "excerpt": "這間診所的醫師很細心",
                            "likeCount": 25,
                            "createdAt": "2026-01-05T12:00:00.000Z",
                            "anonymousSchool": "某大學",
                        }},
                        {"post": {
                            "id": 1002,
                            "title": "冬季穿搭",
                            "excerpt": "大衣推薦",
                            "likeCount": 4,
                            "createdAt": "2026-01-06T09:30:00Z",
                        }},
                    ]
                }
            }
        ]
    },
    {
        "widgets": [
            {
                "forumList": {
                    "items": [
                        # 重複的 id 1001，應該被去重（只留一筆）
                        {"post": {
                            "id": 1001,
                            "title": "玻尿酸心得分享(更新)",
                            "excerpt": "追蹤一個月",
                            "likeCount": 30,
                            "createdAt": "2026-01-05T12:00:00.000Z",
                        }},
                    ]
                }
            }
        ]
    },
]


class TestExtractPosts:
    def test_dedupes_by_id(self):
        posts = DcardCrawler._extract_posts(SAMPLE_BODIES)
        ids = sorted(p["id"] for p in posts)
        assert ids == [1001, 1002]

    def test_ignores_garbage_bodies(self):
        assert DcardCrawler._extract_posts([None, {}, {"widgets": []}, 123]) == []

    def test_handles_missing_forumlist(self):
        bodies = [{"widgets": [{"somethingElse": {}}]}]
        assert DcardCrawler._extract_posts(bodies) == []


class TestParseDt:
    def test_parses_iso_with_ms_and_z(self):
        parsed = DcardCrawler._parse_dt("2026-01-05T12:00:00.000Z")
        assert parsed == datetime(2026, 1, 5, 12, 0, 0)
        assert parsed.tzinfo is None  # 統一存成 naive datetime

    def test_invalid_returns_none(self):
        assert DcardCrawler._parse_dt("not-a-date") is None
        assert DcardCrawler._parse_dt(None) is None
        assert DcardCrawler._parse_dt(12345) is None


class TestUniqueId:
    def test_same_input_same_id(self, crawler):
        first = crawler._generate_unique_id("dcard", "makeup", "http://x/1")
        second = crawler._generate_unique_id("dcard", "makeup", "http://x/1")
        assert first == second

    def test_different_url_different_id(self, crawler):
        first = crawler._generate_unique_id("dcard", "makeup", "http://x/1")
        second = crawler._generate_unique_id("dcard", "makeup", "http://x/2")
        assert first != second


class TestToArticle:
    def test_maps_fields_to_project_shape(self, crawler):
        post = {
            "id": 1001,
            "title": "玻尿酸心得分享",
            "excerpt": "這間診所的醫師很細心",
            "likeCount": 25,
            "createdAt": "2026-01-05T12:00:00.000Z",
            "anonymousSchool": "某大學",
        }

        art = crawler._to_article(post, "makeup")
        assert art["platform_name"] == "dcard"
        assert art["board_name"] == "makeup"
        assert art["title"] == "玻尿酸心得分享"
        assert art["content"] == "這間診所的醫師很細心"
        assert art["push_count"] == 25  # likeCount → push_count
        assert art["author_username"] == "某大學"
        assert art["url"] == "https://www.dcard.tw/f/makeup/p/1001"
        assert art["published_at"] == datetime(2026, 1, 5, 12, 0, 0)
        assert art["unique_id"]  # 有值即可

    def test_author_falls_back_to_anonymous(self, crawler):
        post = {"id": 5, "title": "t", "excerpt": "e", "likeCount": 0, "createdAt": None}
        art = crawler._to_article(post, "dressup")
        assert art["author_username"] == "Dcard 匿名"
        assert art["published_at"] is None
        assert art["content"] == "e"

    def test_missing_like_count_defaults_zero(self, crawler):
        art = crawler._to_article({"id": 9, "title": "t"}, "facelift")
        assert art["push_count"] == 0
        assert art["content"] == ""

    def test_full_content_overrides_excerpt(self, crawler):
        post = {"id": 7, "title": "t", "excerpt": "摘要"}
        art = crawler._to_article(post, "makeup", content="這是進內頁抓到的完整全文")
        assert art["content"] == "這是進內頁抓到的完整全文"

    def test_falls_back_to_excerpt_when_no_full_content(self, crawler):
        post = {"id": 7, "title": "t", "excerpt": "摘要"}
        # content=None 或空字串 → 退回 excerpt
        assert crawler._to_article(post, "makeup", content=None)["content"] == "摘要"
        assert crawler._to_article(post, "makeup", content="")["content"] == "摘要"


class TestCleanContent:
    def test_strips_and_collapses_blank_lines(self):
        raw = "  第一行  \n\n\n  第二行  \n   \n第三行  "
        assert DcardCrawler._clean_content(raw) == "第一行\n第二行\n第三行"

    def test_empty_or_none(self):
        assert DcardCrawler._clean_content(None) == ""
        assert DcardCrawler._clean_content("") == ""
        assert DcardCrawler._clean_content("   \n  \n ") == ""


class TestExtractComments:
    def test_extracts_dedupes_and_skips_empty(self):
        bodies = [
            {"items": [
                {"id": "c1", "content": "這間診所超雷"},
                {"id": "c2", "content": "  價格合理  "},
                {"id": "c3", "content": ""},        # 空內容 → 略過
                {"id": "c4", "content": None},        # None → 略過
            ], "nextKey": "k"},
            {"items": [
                {"id": "c1", "content": "這間診所超雷"},  # 重複 id → 去重
                {"id": "c5", "content": "會回購"},
            ]},
        ]
        assert DcardCrawler._extract_comments(bodies) == ["這間診所超雷", "價格合理", "會回購"]

    def test_handles_list_form_and_garbage(self):
        bodies = [
            [{"id": "a", "content": "留言一"}],  # 有些回應直接是 list
            None, {}, 123, {"items": "not-a-list"},
        ]
        assert DcardCrawler._extract_comments(bodies) == ["留言一"]


class TestMergeContentAndComments:
    def test_merges_content_and_comments(self):
        merged = DcardCrawler._merge_content_and_comments("內文本體", ["讚", "推薦"])
        assert merged == "內文本體\n【留言】\n- 讚\n- 推薦"

    def test_content_only(self):
        assert DcardCrawler._merge_content_and_comments("只有內文", []) == "只有內文"

    def test_comments_only(self):
        # 內文抓失敗但有留言 → 仍保留留言供分析
        merged = DcardCrawler._merge_content_and_comments("", ["留言A"])
        assert merged == "【留言】\n- 留言A"

    def test_both_empty(self):
        assert DcardCrawler._merge_content_and_comments(None, []) == ""
