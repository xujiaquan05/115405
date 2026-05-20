from fastapi import APIRouter, Query

from app.core.database import SessionLocal
from app.crawlers.ptt_crawler import PTTCrawler
from app.services.article_service import create_article, get_or_create_platform, get_or_create_board
from app.services.crawl_log_service import create_crawl_log, finish_crawl_log
from app.websocket.manager import websocket_manager


router = APIRouter(
    prefix="/api/crawler",
    tags=["Crawler"]
)


@router.post("/ptt")
def crawl_ptt_board(
    board: str = Query(default="BeautySalon", description="PTT board name"),
    pages: int = Query(default=1, ge=1, le=5, description="Number of pages to crawl"),
    start_page: int | None = Query(
        default=None,
        description="PTT page number. If empty, crawler starts from latest index.html"
    )
):
    """
    手動觸發 PTT crawler。

    測試 URL:
    POST http://localhost:8000/api/crawler/ptt?board=BeautySalon&pages=1

    為什麼 pages 限制最多 5？
    開發階段避免一次抓太多頁，減少對 PTT 的壓力，也比較容易 debug。
    """
    db = SessionLocal()

    crawl_log = None

    try:
        # 先確保 platform 和 board 存在，方便 crawl_logs 記錄 FK。
        platform = get_or_create_platform(db, "ptt")
        board_obj = get_or_create_board(db, platform.id, board)

        # 建立 running 狀態的 crawl log。
        crawl_log = create_crawl_log(
            db=db,
            platform_id=platform.id,
            board_id=board_obj.id,
            status="running"
        )

        websocket_manager.broadcast_sync({
            "type": "crawler_started",
            "platform": "ptt",
            "board": board,
            "pages": pages,
            "start_page": start_page,
        })

        crawler = PTTCrawler()

        # 開始抓資料。
        crawled_articles = crawler.crawl_board(
            board=board,
            pages=pages,
            start_page=start_page,
            progress_callback=websocket_manager.broadcast_sync,
        )

        new_count = 0
        skipped_count = 0

        # 把 crawler 抓到的文章逐筆存進 database。
        for item in crawled_articles:
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
                published_at=item.get("published_at")
            )

            if is_new:
                new_count += 1
            else:
                skipped_count += 1

        # crawler 成功完成，更新 crawl log。
        finish_crawl_log(
            db=db,
            crawl_log=crawl_log,
            status="success",
            new_count=new_count,
            skipped_count=skipped_count
        )

        websocket_manager.broadcast_sync({
            "type": "crawler_completed",
            "platform": "ptt",
            "board": board,
            "pages": pages,
            "start_page": start_page,
            "total_crawled": len(crawled_articles),
            "new_count": new_count,
            "skipped_count": skipped_count,
        })

        websocket_manager.broadcast_sync({
            "type": "stats_updated",
            "platform": "ptt",
            "board": board,
            "new_count": new_count,
            "skipped_count": skipped_count,
        })

        return {
            "success": True,
            "platform": "ptt",
            "board": board,
            "pages": pages,
            "start_page": start_page,
            "total_crawled": len(crawled_articles),
            "new_count": new_count,
            "skipped_count": skipped_count
        }

    except Exception as e:
        # 如果 crawler 失敗，也要把錯誤寫進 crawl_logs。
        if crawl_log:
            finish_crawl_log(
                db=db,
                crawl_log=crawl_log,
                status="failed",
                error_message=str(e)
            )

        websocket_manager.broadcast_sync({
            "type": "crawler_failed",
            "platform": "ptt",
            "board": board,
            "pages": pages,
            "start_page": start_page,
            "error": str(e),
        })

        return {
            "success": False,
            "error": str(e)
        }

    finally:
        # 不管成功或失敗，最後都要關閉 database session。
        db.close()
