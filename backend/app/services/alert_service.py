# backend/app/services/alert_service.py

import logging
import os
from datetime import timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.time_utils import taiwan_now
from app.models.database_models import Alert, WatchKeyword
from app.services.dashboard_service import (
    get_overview_metrics,
    get_sentiment_distribution,
)


logger = logging.getLogger(__name__)

# 說明：
# 預警門檻，可用環境變數覆寫。
# - WARNING：負面比例達此值 → 黃色警示
# - CRITICAL：負面比例達此值 → 紅色危機
# - MIN_ARTICLES：文章太少時不預警，避免小樣本雜訊
# - DEDUPE_HOURS：同一關鍵字在這段時間內不重複建立預警
WARNING_NEGATIVE = float(os.getenv("ALERT_WARNING_NEGATIVE", "25"))
CRITICAL_NEGATIVE = float(os.getenv("ALERT_CRITICAL_NEGATIVE", "40"))
MIN_ARTICLES = int(os.getenv("ALERT_MIN_ARTICLES", "5"))
DEDUPE_HOURS = int(os.getenv("ALERT_DEDUPE_HOURS", "12"))


def _net_sentiment_score(sentiment: dict) -> int:
    positive = float(sentiment.get("positive") or 0)
    negative = float(sentiment.get("negative") or 0)
    score = 50 + (positive - negative) / 2
    return int(max(0, min(100, round(score))))


def evaluate_keyword(db: Session, keyword: str, days: int) -> dict:
    """
    說明：
    評估單一關鍵字目前的輿情風險，回傳指標與預警等級。

    level：
    - "critical"：負面比例 >= CRITICAL_NEGATIVE
    - "warning" ：負面比例 >= WARNING_NEGATIVE
    - None      ：未達門檻（含文章數太少）
    """

    sentiment = get_sentiment_distribution(db=db, keyword=keyword, days=days)
    overview = get_overview_metrics(db=db, keyword=keyword, days=days)

    negative_ratio = round(float(sentiment.get("negative") or 0), 1)
    score = _net_sentiment_score(sentiment)
    article_count = int(overview.get("total_articles") or 0)

    level = None
    if article_count >= MIN_ARTICLES:
        if negative_ratio >= CRITICAL_NEGATIVE:
            level = "critical"
        elif negative_ratio >= WARNING_NEGATIVE:
            level = "warning"

    return {
        "level": level,
        "negative_ratio": negative_ratio,
        "sentiment_score": score,
        "article_count": article_count,
    }


def _has_recent_alert(db: Session, keyword: str) -> bool:
    since = taiwan_now() - timedelta(hours=DEDUPE_HOURS)
    recent = (
        db.query(Alert)
        .filter(Alert.keyword == keyword)
        .filter(Alert.created_at >= since)
        .first()
    )
    return recent is not None


def run_alert_checks(db: Session) -> list[Alert]:
    """
    說明：
    針對所有啟用中的監控關鍵字執行風險評估，
    達到門檻且近期沒有重複預警時建立 Alert。回傳新建立的預警清單。
    """

    watch_keywords = (
        db.query(WatchKeyword)
        .filter(WatchKeyword.enabled == 1)
        .all()
    )

    created: list[Alert] = []

    for watch in watch_keywords:
        result = evaluate_keyword(db, watch.keyword, watch.days)

        if not result["level"]:
            continue

        if _has_recent_alert(db, watch.keyword):
            continue

        level_label = "危機" if result["level"] == "critical" else "警示"
        alert = Alert(
            keyword=watch.keyword,
            level=result["level"],
            title=f"「{watch.keyword}」負面聲量{level_label}",
            detail=(
                f"近 {watch.days} 天內共 {result['article_count']} 篇討論，"
                f"負面比例達 {result['negative_ratio']}%，"
                f"情緒分數 {result['sentiment_score']} 分。建議盡快檢視負面內容並回應。"
            ),
            negative_ratio=int(round(result["negative_ratio"])),
            sentiment_score=result["sentiment_score"],
            article_count=result["article_count"],
            is_read=0,
            created_at=taiwan_now(),
        )
        db.add(alert)
        created.append(alert)

    if created:
        db.commit()
        for alert in created:
            db.refresh(alert)

    logger.info("Alert check done: %s new alerts", len(created))
    return created


def serialize_alert(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "keyword": alert.keyword,
        "level": alert.level,
        "title": alert.title,
        "detail": alert.detail,
        "negative_ratio": alert.negative_ratio,
        "sentiment_score": alert.sentiment_score,
        "article_count": alert.article_count,
        "is_read": bool(alert.is_read),
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


def serialize_watch_keyword(watch: WatchKeyword) -> dict:
    return {
        "id": watch.id,
        "keyword": watch.keyword,
        "days": watch.days,
        "enabled": bool(watch.enabled),
        "created_at": watch.created_at.isoformat() if watch.created_at else None,
    }
