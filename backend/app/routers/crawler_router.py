from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import func

from app.core.database import SessionLocal
from app.crawlers.ptt_crawler import PTTCrawler
from app.models.database_models import Article, Board, CrawlLog
from app.services.article_service import create_article, get_or_create_board, get_or_create_platform
from app.services.crawl_log_service import create_crawl_log, finish_crawl_log
from app.services.dashboard_service import TARGET_BOARDS, normalize_boards
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
    handled_count = (log.new_count or 0) + (log.skipped_count or 0)
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
):
    db = SessionLocal()

    try:
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

        running_log = (
            db.query(CrawlLog)
            .outerjoin(CrawlLog.board)
            .filter(CrawlLog.status == "running")
            .order_by(CrawlLog.started_at.desc())
            .first()
        )

        board_counts = dict(
            db.query(Board.name, func.count(Article.id))
            .outerjoin(Article, Article.board_id == Board.id)
            .filter(Board.name.in_(TARGET_BOARDS))
            .group_by(Board.name)
            .all()
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
                    "running_board": running_log.board.name if running_log and running_log.board else None,
                    "running_started_at": _format_datetime(running_log.started_at if running_log else None),
                },
                "logs": [_serialize_crawl_log(log) for log in logs],
                "board_counts": [
                    {"board": board, "article_count": board_counts.get(board, 0)}
                    for board in TARGET_BOARDS
                ],
            },
        }
    finally:
        db.close()


def _crawl_one_board(db, board: str, pages: int, start_page: int | None):
    crawl_log = None

    try:
        platform = get_or_create_platform(db, "ptt")
        board_obj = get_or_create_board(db, platform.id, board)

        crawl_log = create_crawl_log(
            db=db,
            platform_id=platform.id,
            board_id=board_obj.id,
            status="running",
        )

        websocket_manager.broadcast_sync({
            "type": "crawler_started",
            "platform": "ptt",
            "board": board,
            "pages": pages,
            "start_page": start_page,
        })

        crawler = PTTCrawler()
        crawled_articles = crawler.crawl_board(
            board=board,
            pages=pages,
            start_page=start_page,
            progress_callback=websocket_manager.broadcast_sync,
        )

        new_count = 0
        skipped_count = 0

        for item in crawled_articles:
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
                new_count += 1
            else:
                skipped_count += 1

        finish_crawl_log(
            db=db,
            crawl_log=crawl_log,
            status="success",
            new_count=new_count,
            skipped_count=skipped_count,
        )

        result = {
            "success": True,
            "platform": "ptt",
            "board": board,
            "pages": pages,
            "start_page": start_page,
            "total_crawled": len(crawled_articles),
            "new_count": new_count,
            "skipped_count": skipped_count,
        }

        websocket_manager.broadcast_sync({
            "type": "crawler_completed",
            **result,
        })

        websocket_manager.broadcast_sync({
            "type": "stats_updated",
            "platform": "ptt",
            "board": board,
            "new_count": new_count,
            "skipped_count": skipped_count,
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
            "platform": "ptt",
            "board": board,
            "pages": pages,
            "start_page": start_page,
            "error": str(error),
        })

        return {
            "success": False,
            "platform": "ptt",
            "board": board,
            "error": str(error),
        }


@router.post("/ptt")
def crawl_ptt_board(
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
):
    db = SessionLocal()

    try:
        selected_boards = normalize_boards(boards) if boards else [board]
        selected_boards = [name for name in selected_boards if name in TARGET_BOARDS]

        results = [
            _crawl_one_board(db=db, board=board_name, pages=pages, start_page=start_page)
            for board_name in selected_boards
        ]

        return {
            "success": all(result.get("success") for result in results),
            "platform": "ptt",
            "boards": selected_boards,
            "pages": pages,
            "start_page": start_page,
            "results": results,
            "total_crawled": sum(result.get("total_crawled", 0) for result in results),
            "new_count": sum(result.get("new_count", 0) for result in results),
            "skipped_count": sum(result.get("skipped_count", 0) for result in results),
        }
    finally:
        db.close()
