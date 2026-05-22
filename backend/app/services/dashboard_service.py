# backend/app/services/dashboard_service.py

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc

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


# Danh sách từ khóa liên quan đến醫美 / làm đẹp
# Note:
# Danh sách này dùng cho keyword cloud.
# Sau này bạn có thể thêm nhiều từ hơn nếu dữ liệu nhiều hơn.
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


def build_keyword_filter(keyword: str):
    """
    Note:
    Tạo điều kiện tìm kiếm keyword trong title hoặc content.

    Vì bài viết PTT có keyword có thể nằm trong:
    - title: tiêu đề bài viết
    - content: nội dung bài viết

    Nên mình dùng OR:
    title chứa keyword HOẶC content chứa keyword.
    """

    keyword_like = f"%{keyword}%"

    return or_(
        Article.title.ilike(keyword_like),
        Article.content.ilike(keyword_like),
    )


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
    Note:
    Tạo khoảng thời gian truy vấn.

    Ví dụ:
    days = 30
    nghĩa là lấy dữ liệu từ 30 ngày trước đến hiện tại.
    """

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    return start_date, end_date


def get_overview_metrics(
    db: Session,
    keyword: str,
    days: int = 30,
    boards: list[str] | None = None,
) -> dict:
    """
    Note:
    Hàm này dùng cho 4 thẻ số liệu tổng quan trên Dashboard.

    Nó sẽ tính:
    1. Tổng số bài liên quan keyword
    2. Trung bình push_count
    3. Số bài negative đơn giản
    4. Tỷ lệ tăng trưởng so với kỳ trước

    Vì Phase 3 chưa dùng LLM, nên negative tạm tính bằng push_count < 0.
    """

    start_date, end_date = get_date_range(days)

    previous_start = start_date - timedelta(days=days)
    previous_end = start_date

    keyword_filter = build_keyword_filter(keyword)

    # Note:
    # Query số bài trong khoảng thời gian hiện tại.
    current_query = (
        db.query(Article)
        .filter(keyword_filter)
        .filter(Article.published_at >= start_date)
        .filter(Article.published_at <= end_date)
    )
    current_query = apply_board_filter(current_query, boards)

    total_articles = current_query.count()

    # Note:
    # Tính average push_count.
    # Nếu không có bài nào thì trả về 0 để tránh lỗi None.
    avg_push_count = (
        current_query.with_entities(func.avg(Article.push_count)).scalar()
    )

    if avg_push_count is None:
        avg_push_count = 0

    # Note:
    # Tạm coi bài có push_count < 0 là negative warning.
    negative_count = (
        current_query
        .filter(Article.push_count < 0)
        .count()
    )

    # Note:
    # Query số bài của kỳ trước để tính growth rate.
    previous_count = (
        db.query(Article)
        .filter(keyword_filter)
        .filter(Article.published_at >= previous_start)
        .filter(Article.published_at < previous_end)
    )
    previous_count = apply_board_filter(previous_count, boards).count()

    # Note:
    # Công thức growth:
    # nếu kỳ trước = 0 và kỳ này > 0 thì tăng 100%
    # nếu cả hai đều 0 thì là 0%
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
    Note:
    Hàm này tính sentiment bằng phương pháp đơn giản dựa trên push_count.

    Quy tắc tạm thời:
    - push_count >= 10  => positive
    - push_count >= 0   => neutral
    - push_count < 0    => negative

    Vì Phase 4 mới dùng LLM phân tích cảm xúc thật,
    Phase 3 chỉ cần sentiment gần đúng để Dashboard có dữ liệu trước.
    """

    start_date, end_date = get_date_range(days)

    keyword_filter = build_keyword_filter(keyword)

    articles = (
        db.query(Article.push_count)
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
        }

    positive = 0
    neutral = 0
    negative = 0

    for article in articles:
        push_count = article.push_count or 0

        if push_count >= 10:
            positive += 1
        elif push_count >= 0:
            neutral += 1
        else:
            negative += 1

    return {
        "positive": round((positive / total) * 100, 2),
        "neutral": round((neutral / total) * 100, 2),
        "negative": round((negative / total) * 100, 2),
        "total": total,
    }


def get_daily_trend(
    db: Session,
    keyword: str,
    days: int = 30,
    boards: list[str] | None = None,
) -> list[dict]:
    """
    Note:
    Hàm này dùng cho biểu đồ đường line chart.

    Nó group bài viết theo ngày:
    2026-05-01 có bao nhiêu bài
    2026-05-02 có bao nhiêu bài
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


def get_hot_articles(
    db: Session,
    keyword: str,
    days: int = 30,
    sort_by: str = "push_count",
    boards: list[str] | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Note:
    Hàm này lấy danh sách bài viết hot / liên quan nhất.

    sort_by hỗ trợ:
    - push_count: bài nhiều推 nhất
    - latest: bài mới nhất
    - relevance: tạm thời cũng ưu tiên push_count

    Sau này nếu có full-text search ranking thì relevance có thể nâng cấp.
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

    # Note:
    # Chọn cách sắp xếp dựa theo sort_by user truyền vào.
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

        # Note:
        # Dashboard không cần hiện full content.
        # Chỉ lấy 120 chữ đầu làm preview cho nhẹ.
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
    Note:
    Hàm này thống kê từ khóa醫美 nào xuất hiện nhiều.

    Cách làm đơn giản:
    - Lấy các bài liên quan keyword chính
    - Đếm mỗi BEAUTY_KEYWORDS xuất hiện trong bao nhiêu bài
    - Sắp xếp từ cao xuống thấp

    Đây là bản dễ hiểu cho Phase 3.
    Sau này nếu muốn mạnh hơn có thể dùng jieba hoặc CKIP để tách từ tiếng Trung.
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


def get_dashboard_full(
    db: Session,
    keyword: str,
    days: int = 30,
    sort_by: str = "push_count",
    boards: list[str] | None = None,
) -> dict:
    """
    Note:
    Đây là hàm tổng hợp cho Dashboard.

    Nó gọi 5 hàm nhỏ:
    1. overview
    2. sentiment
    3. trend
    4. hot_articles
    5. frequent_keywords

    Vì đang dùng SQLAlchemy sync Session,
    mình chạy tuần tự cho đơn giản và ổn định.
    Nếu sau này chuyển sang async DB thì mới dùng asyncio.gather.
    """

    return {
        "overview": get_overview_metrics(db, keyword, days, boards),
        "sentiment": get_sentiment_distribution(db, keyword, days, boards),
        "trend": get_daily_trend(db, keyword, days, boards),
        "hot_articles": get_hot_articles(db, keyword, days, sort_by, boards),
        "keywords": get_frequent_keywords(db, keyword, days, boards),
        "selected_boards": normalize_boards(boards),
    }
