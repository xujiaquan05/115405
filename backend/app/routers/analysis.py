# backend/app/routers/analysis.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database_models import AnalysisResult
from app.services.dashboard_service import (
    get_overview_metrics,
    get_sentiment_distribution,
    normalize_boards,
)
from app.services.llm_analysis_service import analyze_keyword_with_llm
from app.services.sentiment_service import classify_pending_sentiments


router = APIRouter(
    prefix="/api/analysis",
    tags=["LLM Analysis"],
)


@router.get("/keyword")
def analyze_keyword(
    keyword: str = Query(
        default="玻尿酸",
        description="Keyword muốn phân tích, ví dụ: 玻尿酸, 肉毒, 雷射",
    ),
    analysis_type: str = Query(
        default="overview",
        description="Loại phân tích: overview, trend, sentiment",
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Phân tích bài viết trong bao nhiêu ngày gần đây",
    ),
    force_refresh: bool = Query(
        default=False,
        description="True = bỏ qua cache và gọi Gemini lại",
    ),
    boards: list[str] | None = Query(
        default=None,
        description="PTT boards to include. Repeat this query parameter to select multiple boards.",
    ),
    db: Session = Depends(get_db),
):
    """
    Note:
    API chính của Phase 4.

    Ví dụ:
    /api/analysis/keyword?keyword=玻尿酸&analysis_type=overview&days=30

    analysis_type:
    - overview: phân tích tổng hợp
    - trend: phân tích xu hướng
    - sentiment: phân tích cảm xúc
    """

    selected_boards = normalize_boards(boards) if boards else None

    result = analyze_keyword_with_llm(
        db=db,
        keyword=keyword,
        analysis_type=analysis_type,
        days=days,
        force_refresh=force_refresh,
        boards=selected_boards,
    )

    return {
        "status": "success",
        "result": result,
    }


@router.post("/sentiment/refresh")
def refresh_sentiments(
    max_articles: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Số bài chưa chấm sentiment tối đa sẽ gửi cho Gemini trong lần này",
    ),
    db: Session = Depends(get_db),
):
    """
    Note:
    Chấm sentiment thủ công cho các bài chưa có (backfill).
    Bình thường sentiment được chấm tự động sau mỗi lần crawl,
    endpoint này dùng khi DB đã có sẵn bài cũ mà chưa crawl thêm.
    """

    scored_count = classify_pending_sentiments(db, max_articles=max_articles)

    return {
        "status": "success",
        "scored_count": scored_count,
    }


def _extract_topics(result_json: dict) -> list[str]:
    topics = []

    for key in ("hot_topics", "keywords", "consumer_pain_points", "negative_risks"):
        value = result_json.get(key)

        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    topics.append(item)
                elif isinstance(item, dict):
                    topic = (
                        item.get("topic")
                        or item.get("pain_point")
                        or item.get("keyword")
                        or item.get("name")
                        or item.get("title")
                    )

                    if topic:
                        topics.append(str(topic))

    for key in ("rising_topics", "declining_topics"):
        value = result_json.get(key)

        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("topic"):
                    topics.append(str(item["topic"]))

    unique_topics = []

    for topic in topics:
        clean_topic = topic.strip()

        if clean_topic and clean_topic not in unique_topics:
            unique_topics.append(clean_topic)

    return unique_topics[:8]


def _extract_summary(result_json: dict) -> str:
    return (
        result_json.get("summary")
        or result_json.get("trend_summary")
        or result_json.get("pr_warning")
        or "尚無摘要"
    )


def _extract_sentiment_score(result_json: dict, sentiment: dict) -> int:
    raw_score = result_json.get("sentiment_score")

    if isinstance(raw_score, (int, float)):
        return int(max(0, min(100, round(raw_score))))

    positive = float(sentiment.get("positive") or 0)
    negative = float(sentiment.get("negative") or 0)
    score = 50 + (positive * 0.5) - (negative * 0.5)

    return int(max(0, min(100, round(score))))


def _serialize_history_record(record: AnalysisResult, db: Session) -> dict:
    result_json = record.result_json or {}
    overview = get_overview_metrics(db=db, keyword=record.keyword, days=record.days)
    sentiment = get_sentiment_distribution(db=db, keyword=record.keyword, days=record.days)
    negative_ratio = round(float(sentiment.get("negative") or 0), 2)

    return {
        "id": record.id,
        "keyword": record.keyword,
        "analysis_type": record.analysis_type.split(":")[0],
        "days": record.days,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "article_count": overview.get("total_articles", 0),
        "sentiment_score": _extract_sentiment_score(result_json, sentiment),
        "negative_ratio": negative_ratio,
        "topics": _extract_topics(result_json),
        "summary": _extract_summary(result_json),
    }


@router.get("/history")
def analysis_history(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    records = (
        db.query(AnalysisResult)
        .order_by(desc(AnalysisResult.created_at))
        .limit(limit)
        .all()
    )

    items = [_serialize_history_record(record, db) for record in records]

    return {
        "status": "success",
        "data": {
            "records": items,
        },
    }
