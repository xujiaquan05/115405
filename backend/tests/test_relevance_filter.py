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


# ── Dcard 較嚴格門檻（不採整板加權，需關鍵字命中） ──────────────

def test_dcard_post_with_title_keyword_is_kept():
    # 標題含領域關鍵字（×3）→ 分數達門檻 → 收錄
    article = {
        "platform_name": "dcard",
        "board_name": "makeup",
        "title": "玻尿酸保養心得",
        "content": "最近的保養分享",
    }

    result = evaluate_article_relevance(article)

    assert result.is_relevant is True
    assert result.reason == "dcard_keyword_match"


def test_dcard_offtopic_post_is_dropped():
    # Dcard 生活化閒聊、無領域關鍵字 → 被過濾，不進 DB
    article = {
        "platform_name": "dcard",
        "board_name": "makeup",
        "title": "今天心情不好求安慰",
        "content": "最近壓力好大想找人聊聊",
    }

    result = evaluate_article_relevance(article)

    assert result.is_relevant is False
    assert result.reason == "dcard_low_relevance"


def test_dcard_single_excerpt_keyword_is_not_enough():
    # 摘要只命中 1 個關鍵字（×1）< 門檻 2 → 過濾
    article = {
        "platform_name": "dcard",
        "board_name": "dressup",
        "title": "分享今天的日常",
        "content": "配了一件外套",
    }

    result = evaluate_article_relevance(article)

    assert result.is_relevant is False


def test_dcard_facelift_also_requires_keyword():
    # 即使是 Dcard 醫美板(facelift)，仍需關鍵字命中（與 PTT facelift 不同）
    article = {
        "platform_name": "dcard",
        "board_name": "facelift",
        "title": "隨便聊聊",
        "content": "沒什麼特別的",
    }

    result = evaluate_article_relevance(article)

    assert result.is_relevant is False
    assert result.reason == "dcard_low_relevance"
