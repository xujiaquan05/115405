from app.services.relevance_filter import evaluate_article_relevance, is_relevant_article


def test_focused_board_article_is_kept():
    article = {
        "board_name": "BeautySalon",
        "title": "[心得] 夏天保濕精華分享",
        "content": "這次用的是保濕精華，敏感肌也比較穩定。",
    }

    assert is_relevant_article(article) is True


def test_broad_board_needs_domain_keyword():
    article = {
        "board_name": "e-shopping",
        "title": "[閒聊] 一般生活用品購物心得",
        "content": "這篇主要分享文具和收納用品。",
    }

    result = evaluate_article_relevance(article)

    assert result.is_relevant is False
    assert result.reason == "low_relevance_score"


def test_broad_board_with_domain_keyword_is_kept():
    article = {
        "board_name": "Brand",
        "title": "[心得] 精品包包穿搭分享",
        "content": "這次比較不同品牌包包和洋裝搭配。",
    }

    assert is_relevant_article(article) is True


def test_hard_exclude_without_domain_keyword_is_dropped():
    article = {
        "board_name": "BeautySalon",
        "title": "[公告] 板規更新",
        "content": "請大家遵守討論規則。",
    }

    result = evaluate_article_relevance(article)

    assert result.is_relevant is False
    assert result.reason == "hard_exclude_without_domain_keyword"
