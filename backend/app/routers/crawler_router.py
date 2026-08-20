import threading
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.crawlers.registry import get_crawler
from app.models.database_models import Article, Board, CrawlLog, Platform
from app.services.article_service import (
    create_article,
    get_or_create_board,
    get_or_create_platform,
    save_comments,
)
from app.services.audit_service import record_audit
from app.services.auth_service import get_current_user
from app.services.crawl_log_service import create_crawl_log, finish_crawl_log
from app.services.dashboard_service import (
    DCARD_BOARDS,
    MOBILE01_BOARDS,
    TARGET_BOARDS,
    THREADS_BOARDS,
    get_board_overview,
    normalize_boards,
)
from app.services.relevance_filter import evaluate_article_relevance
from app.services.settings_service import get_setting
from app.services.sentiment_service import classify_pending_sentiments
from app.websocket.manager import websocket_manager


router = APIRouter(
    prefix="/api/crawler",
    tags=["Crawler"],
)


def _format_datetime(value):
    if not value:
        return None

    return value.isoformat()


def _serialize_crawl_log(log: CrawlLog):
    started_at = log.started_at
    finished_at = log.finished_at
    duration_seconds = None
    handled_count = (log.new_count or 0) + (log.skipped_count or 0) + (log.filtered_count or 0)
    estimated_pages = max(1, (handled_count + 19) // 20) if handled_count else None

    if started_at and finished_at:
        duration_seconds = max(0, int((finished_at - started_at).total_seconds()))

    return {
        "id": log.id,
        "time": _format_datetime(started_at),
        "finished_at": _format_datetime(finished_at),
        "platform": log.platform.name if log.platform else "ptt",
        "board": log.board.name if log.board else "-",
        "board_label": log.board.display_name if log.board and log.board.display_name else None,
        "status": log.status,
        "pages": estimated_pages,
        "new_count": log.new_count or 0,
        "skipped_count": log.skipped_count or 0,
        "filtered_count": log.filtered_count or 0,
        "error_message": log.error_message,
        "duration_seconds": duration_seconds,
    }


def _format_elapsed_minutes(value):
    if not value:
        return None

    delta_seconds = max(0, int((datetime.now() - value).total_seconds()))
    minutes = delta_seconds // 60

    if minutes < 60:
        return f"{minutes} 分鐘前"

    hours = minutes // 60
    rest_minutes = minutes % 60
    return f"{hours} 小時 {rest_minutes} 分鐘前"


@router.get("/status")
def get_crawler_status(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(CrawlLog)
        .outerjoin(CrawlLog.board)
        .outerjoin(CrawlLog.platform)
        .order_by(CrawlLog.started_at.desc())
        .limit(limit)
        .all()
    )

    last_log = logs[0] if logs else None
    latest_article_at = db.query(func.max(Article.created_at)).scalar()

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_new_count = (
        db.query(func.count(Article.id))
        .filter(Article.created_at >= today_start)
        .scalar()
        or 0
    )

    today_skipped_count = (
        db.query(func.coalesce(func.sum(CrawlLog.skipped_count), 0))
        .filter(CrawlLog.started_at >= today_start)
        .scalar()
        or 0
    )

    today_filtered_count = (
        db.query(func.coalesce(func.sum(CrawlLog.filtered_count), 0))
        .filter(CrawlLog.started_at >= today_start)
        .scalar()
        or 0
    )

    running_log = (
        db.query(CrawlLog)
        .outerjoin(CrawlLog.board)
        .filter(CrawlLog.status == "running")
        .order_by(CrawlLog.started_at.desc())
        .first()
    )

    return {
        "success": True,
        "data": {
            "summary": {
                "status": running_log.status if running_log else "idle",
                "last_crawled_at": _format_datetime(last_log.started_at if last_log else latest_article_at),
                "last_crawled_ago": _format_elapsed_minutes(last_log.started_at if last_log else latest_article_at),
                "today_new_count": today_new_count,
                "today_skipped_count": today_skipped_count,
                "today_filtered_count": today_filtered_count,
                "running_board": running_log.board.name if running_log and running_log.board else None,
                "running_started_at": _format_datetime(running_log.started_at if running_log else None),
            },
            "logs": [_serialize_crawl_log(log) for log in logs],
            # 涵蓋所有平台（PTT / Dcard / Mobile01 / Threads），
            # 舊版只列 PTT 看板，其他平台的數量看不到。
            "board_counts": get_board_overview(db),
        },
    }


def _crawl_one_board(db, platform_name: str, board: str, pages: int, start_page: int | None):
    crawl_log = None

    try:
        platform = get_or_create_platform(db, platform_name)
        board_obj = get_or_create_board(db, platform.id, board)

        crawl_log = create_crawl_log(
            db=db,
            platform_id=platform.id,
            board_id=board_obj.id,
            status="running",
        )

        websocket_manager.broadcast_sync({
            "type": "crawler_started",
            "platform": platform_name,
            "board": board,
            "pages": pages,
            "start_page": start_page,
        })

        crawler = get_crawler(platform_name)
        crawled_articles = crawler.crawl_board(
            board=board,
            pages=pages,
            start_page=start_page,
            progress_callback=websocket_manager.broadcast_sync,
        )

        new_count = 0
        skipped_count = 0
        filtered_count = 0

        for item in crawled_articles:
            relevance = evaluate_article_relevance(item)

            if not relevance.is_relevant:
                filtered_count += 1
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
                new_count += 1
                # 留言另存一張表，供「留言情緒」與「最負面留言」分析。
                save_comments(db, article, item.get("comments") or [])
            else:
                skipped_count += 1

        finish_crawl_log(
            db=db,
            crawl_log=crawl_log,
            status="success",
            new_count=new_count,
            skipped_count=skipped_count,
            filtered_count=filtered_count,
        )

        result = {
            "success": True,
            "platform": platform_name,
            "board": board,
            "pages": pages,
            "start_page": start_page,
            "total_crawled": len(crawled_articles),
            "new_count": new_count,
            "skipped_count": skipped_count,
            "filtered_count": filtered_count,
        }

        websocket_manager.broadcast_sync({
            "type": "crawler_completed",
            **result,
        })

        websocket_manager.broadcast_sync({
            "type": "stats_updated",
            "platform": platform_name,
            "board": board,
            "new_count": new_count,
            "skipped_count": skipped_count,
            "filtered_count": filtered_count,
        })

        return result

    except Exception as error:
        if crawl_log:
            finish_crawl_log(
                db=db,
                crawl_log=crawl_log,
                status="failed",
                error_message=str(error),
            )

        websocket_manager.broadcast_sync({
            "type": "crawler_failed",
            "platform": platform_name,
            "board": board,
            "pages": pages,
            "start_page": start_page,
            "error": str(error),
        })

        return {
            "success": False,
            "platform": platform_name,
            "board": board,
            "error": str(error),
        }


# 說明：
# 爬取在 background task 中執行，因此需要狀態旗標 + lock，
# 避免兩個 request 同時觸發兩批重疊的爬取
# （既加倍打到 PTT，log 也會互相混在一起）。
_crawl_state_lock = threading.Lock()
_crawl_running = False


def _try_start_crawl() -> bool:
    global _crawl_running

    with _crawl_state_lock:
        if _crawl_running:
            return False

        _crawl_running = True
        return True


def _finish_crawl():
    global _crawl_running

    with _crawl_state_lock:
        _crawl_running = False


def _run_crawl_job(platform_name: str, boards: list[str], pages: int, start_page: int | None):
    # 說明：
    # background task 在 response 送出後才執行，
    # 必須自己開關獨立的 session，不能用 request 的 session。
    db = SessionLocal()

    try:
        for board_name in boards:
            _crawl_one_board(
                db=db,
                platform_name=platform_name,
                board=board_name,
                pages=pages,
                start_page=start_page,
            )

        # 說明：
        # 爬取結束後，用 Gemini 為新文章評情緒
        # （還沒評分的舊文章也會被逐步 backfill）。
        # 這個函式會自行吞掉 LLM 錯誤，不會影響爬取工作。
        scored_count = classify_pending_sentiments(db)

        if scored_count:
            websocket_manager.broadcast_sync({
                "type": "stats_updated",
                "reason": "sentiment_scored",
                "scored_count": scored_count,
            })
    finally:
        db.close()
        _finish_crawl()


# 說明：
# 觸發爬蟲會對 PTT 發出大量請求且消耗資源，
# 屬於敏感操作，必須登入才能使用。
@router.post("/ptt")
def crawl_ptt_board(
    background_tasks: BackgroundTasks,
    board: str = Query(default="BeautySalon", description="Single PTT board name"),
    boards: list[str] | None = Query(
        default=None,
        description="Multiple PTT boards. Repeat this query parameter to crawl more than one board.",
    ),
    pages: int = Query(default=1, ge=1, description="Number of pages per board"),
    start_page: int | None = Query(
        default=None,
        description="PTT page number. If empty, crawler starts from latest index.html",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    selected_boards = normalize_boards(boards) if boards else [board]
    selected_boards = [name for name in selected_boards if name in TARGET_BOARDS]

    if not selected_boards:
        raise HTTPException(status_code=400, detail="沒有可爬取的看板，請確認看板名稱。")

    if not _try_start_crawl():
        raise HTTPException(status_code=409, detail="已有爬取任務執行中，請稍後再試。")

    record_audit(
        db,
        actor=current_user,
        action="trigger_crawl",
        target_username=None,
        detail=f"觸發爬取（PTT）：{'、'.join(selected_boards)}（{pages} 頁）",
    )
    db.commit()

    background_tasks.add_task(_run_crawl_job, "ptt", selected_boards, pages, start_page)

    return {
        "success": True,
        "started": True,
        "platform": "ptt",
        "boards": selected_boards,
        "pages": pages,
        "start_page": start_page,
        "message": "爬取任務已開始，進度請透過 WebSocket 或 /api/crawler/status 追蹤。",
    }


def _active_dcard_boards(db: Session) -> list[str]:
    """回傳目前啟用中的 Dcard 看板 alias 清單（管理員可在後台調整）。"""
    rows = (
        db.query(Board.name)
        .join(Platform, Board.platform_id == Platform.id)
        .filter(Platform.name == "dcard", Board.is_active == 1)
        .all()
    )
    names = [name for (name,) in rows]
    return names or list(DCARD_BOARDS.keys())


# 說明：
# 觸發 Dcard 爬蟲。Dcard 位於 Cloudflare 之後，必須開真實瀏覽器（headed），
# 每次僅允許一個爬取任務執行（與 PTT 共用同一個執行旗標）。屬於敏感操作，需登入。
@router.post("/dcard")
def crawl_dcard_board(
    background_tasks: BackgroundTasks,
    board: str = Query(default="makeup", description="Single Dcard forum alias"),
    boards: list[str] | None = Query(
        default=None,
        description="Multiple Dcard forum aliases. Repeat this query parameter for more than one.",
    ),
    pages: int = Query(default=1, ge=1, le=10, description="約每頁 30 篇，pages 越大爬越多"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 部署到無頭環境時可在系統設定關閉 Dcard 爬取。
    if not get_setting(db, "dcard_crawl_enabled"):
        raise HTTPException(status_code=403, detail="Dcard 爬取目前已停用，可於系統設定開啟。")

    allowed = set(_active_dcard_boards(db))
    requested = boards if boards else [board]
    selected_boards = [name for name in dict.fromkeys(requested) if name in allowed]

    if not selected_boards:
        raise HTTPException(status_code=400, detail="沒有可爬取的 Dcard 看板，請確認看板名稱或是否已啟用。")

    if not _try_start_crawl():
        raise HTTPException(status_code=409, detail="已有爬取任務執行中，請稍後再試。")

    record_audit(
        db,
        actor=current_user,
        action="trigger_crawl",
        target_username=None,
        detail=f"觸發爬取（Dcard）：{'、'.join(selected_boards)}（約 {pages * 30} 篇）",
    )
    db.commit()

    background_tasks.add_task(_run_crawl_job, "dcard", selected_boards, pages, None)

    return {
        "success": True,
        "started": True,
        "platform": "dcard",
        "boards": selected_boards,
        "pages": pages,
        "message": "Dcard 爬取任務已開始（會開啟瀏覽器視窗），進度請透過 WebSocket 或 /api/crawler/status 追蹤。",
    }


def _active_mobile01_boards(db: Session) -> list[str]:
    """回傳目前啟用中的 Mobile01 討論區編號清單（管理員可在後台調整）。"""
    rows = (
        db.query(Board.name)
        .join(Platform, Board.platform_id == Platform.id)
        .filter(Platform.name == "mobile01", Board.is_active == 1)
        .all()
    )
    names = [name for (name,) in rows]
    return names or list(MOBILE01_BOARDS.keys())


# 說明：
# 觸發 Mobile01 爬蟲。Mobile01 位於 Akamai 之後會擋掉一般 HTTP 請求，
# 必須開真實瀏覽器擷取頁面，因此同樣共用單一執行旗標。屬於敏感操作，需登入。
@router.post("/mobile01")
def crawl_mobile01_board(
    background_tasks: BackgroundTasks,
    board: str = Query(default="371", description="Mobile01 forum id, e.g. 371"),
    boards: list[str] | None = Query(
        default=None,
        description="Multiple Mobile01 forum ids. Repeat this query parameter for more than one.",
    ),
    pages: int = Query(default=1, ge=1, le=10, description="要爬幾頁列表"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 部署到無頭環境時可在系統設定關閉 Mobile01 爬取。
    if not get_setting(db, "mobile01_crawl_enabled"):
        raise HTTPException(status_code=403, detail="Mobile01 爬取目前已停用，可於系統設定開啟。")

    allowed = set(_active_mobile01_boards(db))
    requested = boards if boards else [board]
    selected_boards = [name for name in dict.fromkeys(requested) if name in allowed]

    if not selected_boards:
        raise HTTPException(status_code=400, detail="沒有可爬取的 Mobile01 討論區，請確認編號或是否已啟用。")

    if not _try_start_crawl():
        raise HTTPException(status_code=409, detail="已有爬取任務執行中，請稍後再試。")

    labels = "、".join(f"{b}（{MOBILE01_BOARDS.get(b, b)}）" for b in selected_boards)
    record_audit(
        db,
        actor=current_user,
        action="trigger_crawl",
        target_username=None,
        detail=f"觸發爬取（Mobile01）：{labels}（{pages} 頁）",
    )
    db.commit()

    background_tasks.add_task(_run_crawl_job, "mobile01", selected_boards, pages, None)

    return {
        "success": True,
        "started": True,
        "platform": "mobile01",
        "boards": selected_boards,
        "pages": pages,
        "message": "Mobile01 爬取任務已開始（會開啟瀏覽器視窗），進度請透過 WebSocket 或 /api/crawler/status 追蹤。",
    }


def _active_threads_keywords(db: Session) -> list[str]:
    """回傳目前啟用中的 Threads 搜尋關鍵字清單（管理員可在後台調整）。"""
    rows = (
        db.query(Board.name)
        .join(Platform, Board.platform_id == Platform.id)
        .filter(Platform.name == "threads", Board.is_active == 1)
        .all()
    )
    names = [name for (name,) in rows]
    return names or list(THREADS_BOARDS.keys())


# 說明：
# 觸發 Threads 爬蟲。Threads 內容由 JS 動態渲染，需開真實瀏覽器讀取搜尋結果
#（未登入即可查看，不需要帳號）。屬於敏感操作，需登入。
@router.post("/threads")
def crawl_threads_keyword(
    background_tasks: BackgroundTasks,
    board: str = Query(default="醫美", description="Threads search keyword"),
    boards: list[str] | None = Query(
        default=None,
        description="Multiple Threads keywords. Repeat this query parameter for more than one.",
    ),
    pages: int = Query(default=1, ge=1, le=10, description="約每頁 25 則貼文"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 部署到無頭環境時可在系統設定關閉 Threads 爬取。
    if not get_setting(db, "threads_crawl_enabled"):
        raise HTTPException(status_code=403, detail="Threads 爬取目前已停用，可於系統設定開啟。")

    allowed = set(_active_threads_keywords(db))
    requested = boards if boards else [board]
    selected_boards = [name for name in dict.fromkeys(requested) if name in allowed]

    if not selected_boards:
        raise HTTPException(status_code=400, detail="沒有可爬取的 Threads 關鍵字，請確認關鍵字或是否已啟用。")

    if not _try_start_crawl():
        raise HTTPException(status_code=409, detail="已有爬取任務執行中，請稍後再試。")

    record_audit(
        db,
        actor=current_user,
        action="trigger_crawl",
        target_username=None,
        detail=f"觸發爬取（Threads）：{'、'.join(selected_boards)}（約 {pages * 25} 則）",
    )
    db.commit()

    background_tasks.add_task(_run_crawl_job, "threads", selected_boards, pages, None)

    return {
        "success": True,
        "started": True,
        "platform": "threads",
        "boards": selected_boards,
        "pages": pages,
        "message": "Threads 爬取任務已開始（會開啟瀏覽器視窗），進度請透過 WebSocket 或 /api/crawler/status 追蹤。",
    }


# 說明：
# 停止並重置爬取狀態。用在爬取「卡住」時（例如後端在爬取途中被重啟，
# DB 留下一筆永遠是 running 的紀錄，導致前端一直顯示執行中、無法開新任務）。
#
# 做兩件事：
# 1. 清掉記憶體中的執行旗標，讓新的爬取可以開始。
# 2. 把 DB 裡卡住的 running 紀錄標記為 failed。
# 注意：若真的有背景執行緒還在跑，Python 無法強制中斷它，但重置後
# 仍可開新任務；卡住的舊任務會自行結束或出錯。
@router.post("/reset")
def reset_crawl(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    global _crawl_running

    with _crawl_state_lock:
        _crawl_running = False

    stuck_logs = db.query(CrawlLog).filter(CrawlLog.status == "running").all()

    record_audit(
        db,
        actor=current_user,
        action="reset_crawl",
        target_username=None,
        detail=f"重置爬取狀態（清除 {len(stuck_logs)} 筆卡住紀錄）",
    )

    for log in stuck_logs:
        log.status = "failed"
        log.error_message = "手動重置爬取狀態"
        if log.finished_at is None:
            log.finished_at = datetime.now()

    db.commit()

    websocket_manager.broadcast_sync({
        "type": "crawler_failed",
        "platform": "ptt",
        "board": "-",
        "error": "手動重置爬取狀態",
    })

    return {
        "status": "success",
        "reset_count": len(stuck_logs),
        "message": "已重置爬取狀態，現在可以開始新的爬取。",
    }
