from fastapi import APIRouter, Query

from app.core.database import SessionLocal
from app.crawlers.ptt_crawler import PTTCrawler
from app.services.article_service import create_article, get_or_create_board, get_or_create_platform
from app.services.crawl_log_service import create_crawl_log, finish_crawl_log
from app.services.dashboard_service import TARGET_BOARDS, normalize_boards
from app.websocket.manager import websocket_manager


router = APIRouter(
    prefix="/api/crawler",
    tags=["Crawler"],
)


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
    pages: int = Query(default=1, ge=1, le=5, description="Number of pages per board"),
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
