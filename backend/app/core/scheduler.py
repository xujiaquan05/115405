# backend/app/core/scheduler.py

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.crawlers.ptt_crawler import PTTCrawler
from app.services.alert_service import run_alert_checks
from app.services.article_service import (
    create_article,
    get_or_create_board,
    get_or_create_platform,
)
from app.services.dashboard_service import TARGET_BOARDS
from app.services.sentiment_service import classify_pending_sentiments


logger = logging.getLogger(__name__)

# 說明：
# 每日自動任務的設定，可用環境變數覆寫：
# - AUTO_CRAWL_ENABLED：是否啟用排程（預設 true）
# - AUTO_CRAWL_HOUR   ：每天幾點執行（台灣時間，預設 3 點）
# - AUTO_CRAWL_PAGES  ：每個看板爬幾頁（預設 2）
AUTO_CRAWL_ENABLED = os.getenv("AUTO_CRAWL_ENABLED", "true").lower() == "true"
AUTO_CRAWL_HOUR = int(os.getenv("AUTO_CRAWL_HOUR", "3"))
AUTO_CRAWL_PAGES = int(os.getenv("AUTO_CRAWL_PAGES", "2"))

_scheduler: BackgroundScheduler | None = None


def _crawl_all_boards(db, pages: int) -> int:
    """
    爬取所有目標看板各 pages 頁，回傳新增文章數。
    出錯的看板會跳過，不影響其他看板。
    """

    crawler = PTTCrawler()
    platform = get_or_create_platform(db, "ptt")
    new_total = 0

    for board_name in TARGET_BOARDS:
        try:
            get_or_create_board(db, platform.id, board_name)
            articles = crawler.crawl_board(board=board_name, pages=pages)

            for item in articles:
                _, is_new = create_article(
                    db=db,
                    unique_id=item["unique_id"],
                    platform_name=item["platform_name"],
                    board_name=item["board_name"],
                    author_username=item["author_username"],
                    title=item["title"],
                    content=item.get("content", ""),
                    url=item["url"],
                    push_count=item.get("push_count", 0),
                    published_at=item.get("published_at"),
                )
                if is_new:
                    new_total += 1
        except Exception:
            logger.exception("Daily crawl failed for board %s", board_name)

    return new_total


def run_daily_job(pages: int = AUTO_CRAWL_PAGES) -> dict:
    """
    每日自動任務：
    1. 爬取所有看板最新文章
    2. 用 Gemini 為新文章評情緒
    3. 對監控關鍵字執行風險評估、必要時建立預警

    自行開關 DB session；任何步驟出錯都會記 log，不讓整個任務中斷。
    """

    db = SessionLocal()

    try:
        new_articles = _crawl_all_boards(db, pages)
        scored = classify_pending_sentiments(db)
        alerts = run_alert_checks(db)

        summary = {
            "new_articles": new_articles,
            "scored": scored,
            "new_alerts": len(alerts),
        }
        logger.info("Daily job finished: %s", summary)
        return summary
    finally:
        db.close()


def start_scheduler():
    """
    在 FastAPI 啟動時呼叫，掛上每日自動任務。
    Render 免費方案閒置會休眠，排程可能不會準時觸發；
    可用 /api/monitor/run-now 手動執行來示範。
    """

    global _scheduler

    if not AUTO_CRAWL_ENABLED:
        logger.info("Auto crawl scheduler disabled (AUTO_CRAWL_ENABLED=false)")
        return

    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(timezone="Asia/Taipei")
    _scheduler.add_job(
        run_daily_job,
        trigger="cron",
        hour=AUTO_CRAWL_HOUR,
        minute=0,
        id="daily_opinion_job",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started: daily job at %02d:00 (Asia/Taipei)", AUTO_CRAWL_HOUR)


def shutdown_scheduler():
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
