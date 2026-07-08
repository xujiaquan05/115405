# backend/app/services/dashboard_service.py

import re
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_, desc

from app.core.time_utils import taiwan_now
from app.models.database_models import Article, Board


TARGET_BOARDS = [
    "facelift",
    "BeautySalon",
    "MakeUp",
    "Mix_Match",
    "fashion",
    "Brand",
    "e-shopping",
    "NailSalon",
    "Mancare",
    "teeth_salon",
]


# 醫美 / 美容相關的關鍵字清單。
# 說明：
# 這份清單用於 keyword cloud，
# 之後資料變多時可以再增加更多關鍵字。
BEAUTY_KEYWORDS = [
    "玻尿酸",
    "肉毒",
    "雷射",
    "皮秒",
    "音波",
    "電波",
    "隆鼻",
    "抽脂",
    "雙眼皮",
    "痘疤",
    "美白",
    "保濕",
    "醫美",
    "診所",
    "術後",
    "副作用",
    "價格",
    "推薦",
]


def split_keyword_terms(keyword: str) -> list[str]:
    terms = [
        term.strip()
        for term in re.split(r"[\s,，、]+", keyword or "")
        if term.strip()
    ]

    return terms or [""]


def build_keyword_filter(keyword: str):
    """
    說明：
    建立在 title 或 content 中搜尋 keyword 的條件。

    PTT 文章的關鍵字可能出現在：
    - title: 文章標題
    - content: 文章內文

    所以用 OR：
    title 包含 keyword 或 content 包含 keyword。
    """

    keyword_filters = []

    for term in split_keyword_terms(keyword):
        keyword_like = f"%{term}%"
        keyword_filters.extend([
            Article.title.ilike(keyword_like),
            Article.content.ilike(keyword_like),
        ])

    return or_(*keyword_filters)


def normalize_boards(boards: list[str] | None = None) -> list[str]:
    if not boards:
        return TARGET_BOARDS

    valid_boards = []

    for board in boards:
        if board in TARGET_BOARDS and board not in valid_boards:
            valid_boards.append(board)

    return valid_boards or TARGET_BOARDS


def apply_board_filter(query, boards: list[str] | None = None):
    board_names = normalize_boards(boards)
    return query.filter(Article.board.has(Board.name.in_(board_names)))


def get_date_range(days: int):
    """
    說明：
    建立查詢的時間區間。

    例如：
    days = 30
    表示取最近 30 天到現在的資料。
    """

    end_date = taiwan_now()
    start_date = end_date - timedelta(days=days)

    return start_date, end_date


def get_overview_metrics(
    db: Session,
    keyword: str,
    days: int = 30,
    boards: list[str] | None = None,
) -> dict:
    """
    說明：
    提供 Dashboard 上方 4 張總覽數據卡的資料。

    計算內容：
    1. 與 keyword 相關的文章總數
    2. 平均 push_count
    3. 負面文章數
    4. 相較上一期的成長率
    """

    start_date, end_date = get_date_range(days)

    previous_start = start_date - timedelta(days=days)
    previous_end = start_date

    keyword_filter = build_keyword_filter(keyword)

    # 查詢目前時間區間內的文章數。
    current_query = (
        db.query(Article)
        .filter(keyword_filter)
        .filter(Article.published_at >= start_date)
        .filter(Article.published_at <= end_date)
    )
    current_query = apply_board_filter(current_query, boards)

    total_articles = current_query.count()

    # 計算平均 push_count；
    # 沒有任何文章時回傳 0，避免 None 造成錯誤。
    avg_push_count = (
        current_query.with_entities(func.avg(Article.push_count)).scalar()
    )

    if avg_push_count is None:
        avg_push_count = 0

    # 優先使用 LLM 評出的 sentiment；
    # 還沒評分的文章（NULL）暫時 fallback 回 push_count < 0 規則。
    negative_count = (
        current_query
        .filter(
            or_(
                Article.sentiment == "negative",
                and_(Article.sentiment.is_(None), Article.push_count < 0),
            )
        )
        .count()
    )

    # 查詢上一期的文章數，用來計算成長率。
    previous_count = (
        db.query(Article)
        .filter(keyword_filter)
        .filter(Article.published_at >= previous_start)
        .filter(Article.published_at < previous_end)
    )
    previous_count = apply_board_filter(previous_count, boards).count()

    # 成長率公式：
    # 上一期 = 0 且這一期 > 0 時視為成長 100%；
    # 兩期都是 0 時為 0%。
    if previous_count == 0:
        growth_rate = 100 if total_articles > 0 else 0
    else:
        growth_rate = round(
            ((total_articles - previous_count) / previous_count) * 100,
            2
        )

    return {
        "total_articles": total_articles,
        "avg_push_count": round(float(avg_push_count), 2),
        "negative_count": negative_count,
        "growth_rate": growth_rate,
        "days": days,
        "keyword": keyword,
        "boards": normalize_boards(boards),
    }


def get_sentiment_distribution(
    db: Session,
    keyword: str,
    days: int = 30,
    boards: list[str] | None = None,
) -> dict:
    """
    說明：
    Sentiment 優先使用 LLM 評分結果（articles.sentiment 欄位，
    由 sentiment_service 在每次爬取後評分）。

    還沒評分的文章（sentiment NULL）暫時 fallback 回 push_count：
    - push_count >= 10  => positive
    - push_count >= 0   => neutral
    - push_count < 0    => negative

    ai_rated_percent 表示結果中有多少 % 的文章
    是由 LLM 真正評分的。
    """

    start_date, end_date = get_date_range(days)

    keyword_filter = build_keyword_filter(keyword)

    articles = (
        db.query(Article.push_count, Article.sentiment)
        .filter(keyword_filter)
        .filter(Article.published_at >= start_date)
        .filter(Article.published_at <= end_date)
    )
    articles = apply_board_filter(articles, boards).all()

    total = len(articles)

    if total == 0:
        return {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "total": 0,
            "ai_rated_percent": 0,
        }

    positive = 0
    neutral = 0
    negative = 0
    ai_rated = 0

    for row in articles:
        sentiment = row.sentiment

        if sentiment in ("positive", "neutral", "negative"):
            ai_rated += 1
        else:
            push_count = row.push_count or 0

            if push_count >= 10:
                sentiment = "positive"
            elif push_count >= 0:
                sentiment = "neutral"
            else:
                sentiment = "negative"

        if sentiment == "positive":
            positive += 1
        elif sentiment == "neutral":
            neutral += 1
        else:
            negative += 1

    return {
        "positive": round((positive / total) * 100, 2),
        "neutral": round((neutral / total) * 100, 2),
        "negative": round((negative / total) * 100, 2),
        "total": total,
        "ai_rated_percent": round((ai_rated / total) * 100, 2),
    }


def get_daily_trend(
    db: Session,
    keyword: str,
    days: int = 30,
    boards: list[str] | None = None,
) -> list[dict]:
    """
    說明：
    提供折線圖（line chart）用的資料。

    把文章依日期分組：
    2026-05-01 有幾篇
    2026-05-02 有幾篇
    ...
    """

    start_date, end_date = get_date_range(days)

    keyword_filter = build_keyword_filter(keyword)

    results = (
        db.query(
            func.date(Article.published_at).label("date"),
            func.count(Article.id).label("count"),
        )
        .filter(keyword_filter)
        .filter(Article.published_at >= start_date)
        .filter(Article.published_at <= end_date)
        .group_by(func.date(Article.published_at))
        .order_by(func.date(Article.published_at))
    )
    results = apply_board_filter(results, boards).all()

    trend = []

    for row in results:
        trend.append({
            "date": row.date.strftime("%Y-%m-%d"),
            "count": row.count,
        })

    return trend


def get_keyword_trends(
    db: Session,
    keyword: str,
    days: int = 30,
    boards: list[str] | None = None,
) -> list[dict]:
    """
    Note:
    回傳每個 keyword 各自的 trend，讓前端畫多條折線。
    每個 keyword 都獨立依 title/content 查詢。
    """

    trends = []
    start_date, end_date = get_date_range(days)

    for term in split_keyword_terms(keyword):
        term_like = f"%{term}%"

        query = (
            db.query(
                func.date(Article.published_at).label("date"),
                func.count(Article.id).label("count"),
            )
            .filter(
                or_(
                    Article.title.ilike(term_like),
                    Article.content.ilike(term_like),
                )
            )
            .filter(Article.published_at >= start_date)
            .filter(Article.published_at <= end_date)
            .group_by(func.date(Article.published_at))
            .order_by(func.date(Article.published_at))
        )

        rows = apply_board_filter(query, boards).all()

        trends.append({
            "keyword": term,
            "trend": [
                {
                    "date": row.date.strftime("%Y-%m-%d"),
                    "count": row.count,
                }
                for row in rows
            ],
        })

    return trends


def get_hot_articles(
    db: Session,
    keyword: str,
    days: int = 30,
    sort_by: str = "push_count",
    boards: list[str] | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    說明：
    取得熱門 / 最相關的文章列表。

    sort_by 支援：
    - push_count: 推文數最多
    - latest: 最新文章
    - relevance: 暫時也以 push_count 優先

    之後若有 full-text search ranking，relevance 可以再升級。
    """

    start_date, end_date = get_date_range(days)

    keyword_filter = build_keyword_filter(keyword)

    query = (
        db.query(Article)
        .filter(keyword_filter)
        .filter(Article.published_at >= start_date)
        .filter(Article.published_at <= end_date)
    )
    query = apply_board_filter(query, boards)

    # 依 user 傳入的 sort_by 選擇排序方式。
    if sort_by == "latest":
        query = query.order_by(desc(Article.published_at))
    elif sort_by == "relevance":
        query = query.order_by(desc(Article.push_count))
    else:
        query = query.order_by(desc(Article.push_count))

    articles = query.limit(limit).all()

    result = []

    for article in articles:
        content = article.content or ""

        # Dashboard 不需要顯示完整內文，
        # 只取前 120 個字當作 preview，減少傳輸量。
        preview = content[:120]

        if len(content) > 120:
            preview += "..."

        result.append({
            "id": article.id,
            "title": article.title,
            "board": article.board.name if article.board else "",
            "author": article.author.username if article.author else "unknown",
            "push_count": article.push_count,
            "published_at": article.published_at.strftime("%Y-%m-%d %H:%M:%S")
            if article.published_at else None,
            "url": article.url,
            "preview": preview,
        })

    return result


def get_frequent_keywords(
    db: Session,
    keyword: str,
    days: int = 30,
    boards: list[str] | None = None,
) -> list[dict]:
    """
    說明：
    統計哪些醫美關鍵字出現得最多。

    簡單做法：
    - 取得與主 keyword 相關的文章
    - 計算每個 BEAUTY_KEYWORDS 出現在幾篇文章中
    - 由高到低排序

    這是容易理解的簡化版本；
    之後若要更精準，可以改用 jieba 或 CKIP 做中文斷詞。
    """

    start_date, end_date = get_date_range(days)

    keyword_filter = build_keyword_filter(keyword)

    articles = (
        db.query(Article.title, Article.content)
        .filter(keyword_filter)
        .filter(Article.published_at >= start_date)
        .filter(Article.published_at <= end_date)
    )
    articles = apply_board_filter(articles, boards).all()

    keyword_count = {}

    for beauty_keyword in BEAUTY_KEYWORDS:
        count = 0

        for article in articles:
            title = article.title or ""
            content = article.content or ""
            text = title + " " + content

            if beauty_keyword in text:
                count += 1

        if count > 0:
            keyword_count[beauty_keyword] = count

    result = [
        {
            "keyword": key,
            "count": value,
        }
        for key, value in keyword_count.items()
    ]

    result.sort(key=lambda item: item["count"], reverse=True)

    return result[:20]


def get_data_status(
    db: Session,
    boards: list[str] | None = None,
) -> dict:
    query = db.query(Article.published_at).filter(Article.published_at.isnot(None))
    query = apply_board_filter(query, boards)
    latest_published_at = (
        query.order_by(desc(Article.published_at))
        .limit(1)
        .scalar()
    )

    return {
        "latest_published_at": latest_published_at.strftime("%Y-%m-%d %H:%M")
        if latest_published_at else None,
        "status": "normal" if latest_published_at else "empty",
        "source": "PTT",
        "boards": normalize_boards(boards),
    }


def get_dashboard_full(
    db: Session,
    keyword: str,
    days: int = 30,
    sort_by: str = "push_count",
    boards: list[str] | None = None,
) -> dict:
    """
    說明：
    Dashboard 的彙總函式。

    它呼叫以下幾個小函式：
    1. overview
    2. sentiment
    3. trend
    4. hot_articles
    5. frequent_keywords

    因為使用的是 SQLAlchemy sync Session，
    為求簡單穩定採取循序執行；
    之後若改用 async DB 再考慮 asyncio.gather。
    """

    return {
        "overview": get_overview_metrics(db, keyword, days, boards),
        "sentiment": get_sentiment_distribution(db, keyword, days, boards),
        "trend": get_daily_trend(db, keyword, days, boards),
        "keyword_trends": get_keyword_trends(db, keyword, days, boards),
        "hot_articles": get_hot_articles(db, keyword, days, sort_by, boards),
        "keywords": get_frequent_keywords(db, keyword, days, boards),
        "data_status": get_data_status(db, boards),
        "selected_boards": normalize_boards(boards),
    }
