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
from app.services.dashboard_service import get_active_board_names
from app.services.sentiment_service import classify_pending_sentiments
from app.services.settings_service import get_setting


logger = logging.getLogger(__name__)

# 說明：
# 每日自動任務的設定（是否啟用 / 幾點執行 / 每個看板爬幾頁）
# 改由「系統設定」提供，管理員可在後台調整；預設值仍沿用環境變數。
JOB_ID = "daily_opinion_job"

_scheduler: BackgroundScheduler | None = None


def _crawl_all_boards(db, pages: int) -> int:
    """
    爬取所有目標看板各 pages 頁，回傳新增文章數。
    出錯的看板會跳過，不影響其他看板。
    """

    crawler = PTTCrawler()
    platform = get_or_create_platform(db, "ptt")
    new_total = 0

    for board_name in get_active_board_names(db):
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


def run_daily_job(pages: int | None = None, force: bool = False) -> dict:
    """
    每日自動任務：
    1. 爬取所有看板最新文章
    2. 用 Gemini 為新文章評情緒
    3. 對監控關鍵字執行風險評估、必要時建立預警

    啟用狀態與爬取頁數即時從系統設定讀取。
    force=True 時忽略「停用」設定（手動觸發時使用）。
    自行開關 DB session；任何步驟出錯都會記 log，不讓整個任務中斷。
    """

    db = SessionLocal()

    try:
        if not force and not get_setting(db, "auto_crawl_enabled"):
            logger.info("Daily job skipped: auto_crawl_enabled is off")
            return {"skipped": True}

        effective_pages = pages if pages is not None else get_setting(db, "auto_crawl_pages")

        new_articles = _crawl_all_boards(db, effective_pages)
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


def _read_schedule_hour() -> int:
    # 從系統設定讀取排程時間（開獨立 session）。
    db = SessionLocal()
    try:
        return int(get_setting(db, "auto_crawl_hour"))
    finally:
        db.close()


def start_scheduler():
    """
    在 FastAPI 啟動時呼叫，掛上每日自動任務。
    排程一律建立；實際是否執行由 run_daily_job 依系統設定 auto_crawl_enabled 決定，
    這樣管理員在後台開關時不需重啟。
    Render 免費方案閒置會休眠，排程可能不會準時觸發；
    可用 /api/monitor/run-now 手動執行來示範。
    """

    global _scheduler

    if _scheduler is not None:
        return

    hour = _read_schedule_hour()
    _scheduler = BackgroundScheduler(timezone="Asia/Taipei")
    _scheduler.add_job(
        run_daily_job,
        trigger="cron",
        hour=hour,
        minute=0,
        id=JOB_ID,
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started: daily job at %02d:00 (Asia/Taipei)", hour)


def reschedule_daily_job(hour: int) -> bool:
    """
    重新設定每日任務的執行時間。管理員在後台改「執行時間」後呼叫。
    以 try/except 包住，避免排程操作失敗影響到 API 請求。
    """

    if _scheduler is None:
        return False

    try:
        _scheduler.reschedule_job(JOB_ID, trigger="cron", hour=hour, minute=0)
        logger.info("Daily job rescheduled to %02d:00 (Asia/Taipei)", hour)
        return True
    except Exception:
        logger.exception("Failed to reschedule daily job")
        return False


def shutdown_scheduler():
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
