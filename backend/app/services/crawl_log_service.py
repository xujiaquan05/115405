from datetime import datetime

from app.models.database_models import CrawlLog


def create_crawl_log(db, platform_id=None, board_id=None, status="running"):
    """
    在 crawler 開始執行時建立 log。

    為什麼需要 log？
    方便之後確認 crawler 是否有執行、什麼時候執行、
    成功還是失敗、抓到多少篇新文章。
    """
    crawl_log = CrawlLog(
        platform_id=platform_id,
        board_id=board_id,
        status=status,
        new_count=0,
        skipped_count=0,
        started_at=datetime.now()
    )

    db.add(crawl_log)
    db.commit()
    db.refresh(crawl_log)

    return crawl_log


def finish_crawl_log(
    db,
    crawl_log,
    status="success",
    new_count=0,
    skipped_count=0,
    error_message=None
):
    """
    在 crawler 執行結束後更新 log。

    成功時：
        status = success

    失敗時：
        status = failed
        error_message = 錯誤內容
    """
    crawl_log.status = status
    crawl_log.new_count = new_count
    crawl_log.skipped_count = skipped_count
    crawl_log.error_message = error_message
    crawl_log.finished_at = datetime.now()

    db.commit()
    db.refresh(crawl_log)

    return crawl_log
