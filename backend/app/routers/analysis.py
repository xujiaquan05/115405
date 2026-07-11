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
from app.services.auth_service import get_current_user
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
        description="要分析的關鍵字，例如：玻尿酸、肉毒、雷射",
    ),
    analysis_type: str = Query(
        default="overview",
        description="分析類型：overview、trend、sentiment",
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="分析最近幾天內的文章",
    ),
    force_refresh: bool = Query(
        default=False,
        description="True = 跳過 cache，重新呼叫 Gemini",
    ),
    boards: list[str] | None = Query(
        default=None,
        description="要包含的 PTT 看板，重複此參數可選多個看板。",
    ),
    db: Session = Depends(get_db),
):
    """
    說明：
    LLM 關鍵字分析的主要 API。

    例如：
    /api/analysis/keyword?keyword=玻尿酸&analysis_type=overview&days=30

    analysis_type：
    - overview: 綜合分析
    - trend: 趨勢分析
    - sentiment: 情緒分析
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


# 說明：
# 手動評分會大量呼叫 Gemini（消耗 API 額度），必須登入才能使用。
@router.post("/sentiment/refresh", dependencies=[Depends(get_current_user)])
def refresh_sentiments(
    max_articles: int = Query(
        default=100,
        ge=1,
        le=500,
        description="這次最多送給 Gemini 評分的未評分文章數",
    ),
    db: Session = Depends(get_db),
):
    """
    說明：
    手動為還沒有 sentiment 的文章評分（backfill）。
    正常情況下 sentiment 會在每次爬取後自動評分，
    這個 endpoint 用在 DB 已有舊文章但尚未再爬取的情況。
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
