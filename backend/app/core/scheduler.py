# backend/app/core/scheduler.py

import logging
import os
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal, close_transaction
from app.core.shutdown import CrawlAborted, clear_stop, request_stop, stop_requested
from app.core.time_utils import taiwan_now
from app.crawlers.registry import get_crawler
from app.services import lock_service
from app.services.alert_service import run_alert_checks
from app.services.article_service import (
    create_article,
    get_or_create_board,
    get_or_create_platform,
    save_comments,
)
from app.services.dashboard_service import get_active_crawl_targets
from app.services.embedding_service import embed_pending_articles
from app.services.relevance_filter import evaluate_article_relevance
from app.services.sentiment_service import (
    classify_pending_comments,
    classify_pending_sentiments,
)
from app.services.settings_service import get_internal_value, get_setting, set_internal_value

logger = logging.getLogger(__name__)

# 說明：
# 每日自動任務的設定（是否啟用 / 幾點執行 / 每個看板爬幾頁）
# 改由「系統設定」提供，管理員可在後台調整；預設值仍沿用環境變數。
JOB_ID = "daily_opinion_job"

# 補跑用的一次性任務 id。
CATCHUP_JOB_ID = "daily_opinion_catchup"

# 記錄「每日任務最後成功執行的日期」（YYYY-MM-DD，台灣時間）。
LAST_RUN_KEY = "last_daily_job_date"

# 後端啟動後隔多久才補跑。
# 不立刻執行是為了讓服務先能回應請求；開發時用 --reload 頻繁重啟，
# 也不會每存一次檔就馬上開一堆瀏覽器。
CATCHUP_DELAY_SECONDS = int(os.getenv("STARTUP_CATCHUP_DELAY", "20"))


def _today() -> str:
    return taiwan_now().strftime("%Y-%m-%d")


def has_run_today(db) -> bool:
    """今天是否已經成功跑過每日任務。

    只認每日任務自己的紀錄，不看 crawl_logs：
    手動爬取單一看板和「跑完整套流程」不是同一件事。
    """
    return get_internal_value(db, LAST_RUN_KEY) == _today()

_scheduler: BackgroundScheduler | None = None


def _crawl_all_boards(db, pages: int) -> int:
    """
    爬取所有啟用中的目標看板各 pages 頁（跨平台：ptt / dcard），回傳新增文章數。
    依平台挑選對應爬蟲；出錯的看板會跳過，不影響其他看板。
    """

    new_total = 0

    # Dcard / Mobile01 需真實瀏覽器，部署到無頭環境時可在系統設定關閉，
    # 避免每日排程白跑並產生錯誤 log。
    browser_platform_enabled = {
        "dcard": get_setting(db, "dcard_crawl_enabled"),
        "mobile01": get_setting(db, "mobile01_crawl_enabled"),
        "threads": get_setting(db, "threads_crawl_enabled"),
    }

    # 先把目標讀成 list 並結束交易，之後才進入耗時的爬取階段。
    targets = list(get_active_crawl_targets(db))
    close_transaction(db)

    for platform_name, board_name in targets:
        if not browser_platform_enabled.get(platform_name, True):
            continue

        # 系統要關閉時就不要再開下一個看板（每個看板都可能跑好幾分鐘）。
        if stop_requested():
            logger.info("Crawl stopped before board %s: shutdown requested", board_name)
            break

        try:
            platform = get_or_create_platform(db, platform_name)
            get_or_create_board(db, platform.id, board_name)

            # 一個看板一個交易：爬取本身不碰資料庫，不該讓交易跟著開好幾分鐘。
            # （get_or_create_* 只有在「需要新增」時才會 commit，
            #   看板早就存在的日常情況下，這裡不主動結束就會一直開著。）
            close_transaction(db)

            crawler = get_crawler(platform_name)
            articles = crawler.crawl_board(board=board_name, pages=pages)

            for item in articles:
                # 先過濾不相關 / 版務公告文，通過後才寫入 DB（與手動爬取一致）。
                if not evaluate_article_relevance(item).is_relevant:
                    continue

                article, is_new = create_article(
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
                    save_comments(db, article, item.get("comments") or [])

            # 收尾這個看板的交易，下一個看板從乾淨的狀態開始。
            close_transaction(db)
        except CrawlAborted:
            # 不是錯誤，是系統關閉時主動收手；已寫入的文章保留。
            logger.info("Crawl aborted while crawling board %s", board_name)
            db.rollback()
            break
        except Exception:
            logger.exception("Daily crawl failed for board %s", board_name)
            # 沒有 rollback 的話，這個看板留下的失敗交易會讓
            # 下一個看板的每一次查詢都直接拋 PendingRollbackError。
            db.rollback()

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

        # 和手動爬取共用同一把鎖。
        # 少了這一步，排程在凌晨開跑時，若剛好有人從後台按下爬取，
        # 兩批就會同時進行——正是這把鎖要避免的情況。
        if not lock_service.try_acquire(db, lock_service.CRAWL_LOCK):
            logger.info("Daily job skipped: another crawl is already running")
            return {"skipped": True, "reason": "crawl_in_progress"}

        try:
            new_articles = _crawl_all_boards(db, effective_pages)
        finally:
            # 爬取結束就放開，後面的評分與預警不需要佔著鎖。
            lock_service.release(db, lock_service.CRAWL_LOCK)

        # 被中止的話就到此為止：不呼叫 Gemini（省額度），
        # 也不記錄「今天已完成」，讓下次啟動能再補跑一次。
        if stop_requested():
            logger.info("Daily job aborted after crawling %d new articles", new_articles)
            return {"aborted": True, "new_articles": new_articles}

        scored = classify_pending_sentiments(db)
        scored_comments = classify_pending_comments(db)
        # 新文章要有向量，RAG 的語意檢索才找得到它們。
        embedded = embed_pending_articles(db)
        alerts = run_alert_checks(db)

        summary = {
            "new_articles": new_articles,
            "scored": scored,
            "scored_comments": scored_comments,
            "embedded": embedded,
            "new_alerts": len(alerts),
        }
        # 記錄完成日期，讓下次啟動知道今天不用補跑。
        set_internal_value(db, LAST_RUN_KEY, _today())

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

    # 新的行程重新開始，清掉上一輪可能留下的停止旗標。
    clear_stop()

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

    _schedule_startup_catchup()


def _schedule_startup_catchup() -> None:
    """若今天還沒跑過每日任務，啟動後補跑一次。

    為什麼需要這個？
    排程只在後端執行中才會觸發。在本機使用時，半夜三點電腦通常是關的，
    而 APScheduler 預設不會補跑錯過的排程——結果是排程設定好了卻從未執行
    （實際查資料庫：所有爬取都發生在使用者操作的時段，凌晨三點一次也沒有）。

    有了補跑，只要每天開一次後端就會收到當天的資料，
    不必讓電腦整夜開著。
    """
    db = SessionLocal()

    try:
        if not get_setting(db, "auto_crawl_enabled"):
            return

        if not get_setting(db, "startup_catchup_enabled"):
            return

        if has_run_today(db):
            logger.info("Startup catch-up skipped: daily job already ran today")
            return
    finally:
        db.close()

    run_at = taiwan_now() + timedelta(seconds=CATCHUP_DELAY_SECONDS)

    _scheduler.add_job(
        run_daily_job,
        trigger="date",
        run_date=run_at,
        id=CATCHUP_JOB_ID,
        # 重啟時若前一次補跑還排在佇列中，換成新的即可，不要排兩次。
        replace_existing=True,
    )
    logger.info("Daily job has not run today; catching up in %ds", CATCHUP_DELAY_SECONDS)


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

    # 先叫進行中的爬取收手，再關排程。
    # 少了這一步，shutdown(wait=False) 只會停止「派新工作」，
    # 正在跑的爬取仍會被 concurrent.futures 在直譯器結束時 join——
    # 行程於是停止服務卻死不掉，還佔著 8000 埠，
    # 前端每個請求都石沉大海（--reload 存檔重啟時最容易遇到）。
    request_stop()

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
