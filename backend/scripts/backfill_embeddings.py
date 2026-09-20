"""一次性工具：為既有文章產生語意向量（embedding）。

為什麼需要？
向量是在爬取流程結束時順便產生的，所以只有「之後」爬到的文章才有。
資料庫裡既有的文章沒有向量，RAG 的語意檢索就看不到它們——
混合檢索會自動退回純關鍵字，功能不會壞，但等於沒有生效。

用法（在 backend 目錄下）：
    venv\\Scripts\\python.exe scripts\\backfill_embeddings.py --dry-run
    venv\\Scripts\\python.exe scripts\\backfill_embeddings.py

注意：
- 會實際呼叫 Gemini embedding API 並消耗額度，先用 --dry-run 確認數量。
- 文章會先切成數段，一次送 50 段；一篇長文可能佔掉好幾段，
  所以要打幾次 API 是看段落數而不是文章數（--dry-run 會兩個都印）。
- 每批寫入就 commit，中途停掉不會丟失已完成的部分。
  同一篇文章的所有段落一定在同一批，不會留下只做一半的文章。
"""

import argparse
import logging
import math
import sys
import time
from pathlib import Path

# 讓這個腳本不論從哪裡執行都能 import 到 app 套件。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.database_models import Article, ArticleChunk  # noqa: E402
from app.services.embedding_service import (  # noqa: E402
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBED_BATCH_SIZE,
    MAX_CHUNKS_PER_ARTICLE,
    count_pending_embeddings,
    embed_pending_articles,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s | %(message)s")
logger = logging.getLogger("backfill_embeddings")

# 連續幾輪待處理數量都沒有減少就放棄，避免額度用完後空轉。
MAX_STALLED_ROUNDS = 3
RETRY_WAIT_SECONDS = 60


def estimate_chunks(db) -> int:
    """估算待處理文章會切成幾段，用來推算 API 呼叫次數。

    算式與 split_into_chunks 相同：第一段之後每次前進
    (CHUNK_SIZE - CHUNK_OVERLAP) 個字，直到覆蓋完整篇。
    """
    step = CHUNK_SIZE - CHUNK_OVERLAP
    lengths = (
        db.query(func.length(func.coalesce(Article.content, "")))
        .outerjoin(ArticleChunk, ArticleChunk.article_id == Article.id)
        .filter(ArticleChunk.article_id.is_(None))
        .all()
    )

    total = 0

    for (length,) in lengths:
        count = 1 + math.ceil(max((length or 0) - CHUNK_SIZE, 0) / step)
        total += min(count, MAX_CHUNKS_PER_ARTICLE)

    return total


def backfill(limit: int | None, pause: float) -> int:
    db = SessionLocal()

    try:
        pending = count_pending_embeddings(db)
        logger.info("尚未產生向量：%d 篇", pending)

        created_total = 0
        stalled_rounds = 0

        while True:
            if limit is not None and created_total >= limit:
                logger.info("已達 --limit %d，停止。", limit)
                break

            before = count_pending_embeddings(db)

            if before == 0:
                logger.info("所有文章都已有向量。")
                break

            try:
                # 一次只送一批，節奏握在自己手上，避免撞到每分鐘請求上限。
                created = embed_pending_articles(
                    db, max_articles=EMBED_BATCH_SIZE, batch_size=EMBED_BATCH_SIZE
                )
            except Exception:
                logger.exception("這一批失敗，等 %d 秒後再試", RETRY_WAIT_SECONDS)
                time.sleep(RETRY_WAIT_SECONDS)
                continue

            remaining = count_pending_embeddings(db)

            if remaining >= before:
                stalled_rounds += 1
                logger.warning(
                    "這一批待處理數量沒有減少（第 %d/%d 次），可能是額度用完",
                    stalled_rounds,
                    MAX_STALLED_ROUNDS,
                )

                if stalled_rounds >= MAX_STALLED_ROUNDS:
                    logger.error("連續 %d 批都沒有進展，停止以免空轉消耗額度。", MAX_STALLED_ROUNDS)
                    break

                time.sleep(RETRY_WAIT_SECONDS)
                continue

            stalled_rounds = 0
            created_total += created
            logger.info("本批 +%d｜累計 %d｜剩餘 %d", created, created_total, remaining)

            if remaining:
                time.sleep(pause)

        return created_total
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="為既有文章產生語意向量")
    parser.add_argument("--limit", type=int, default=None, help="最多處理幾篇（預設：全部）")
    parser.add_argument("--pause", type=float, default=2.0, help="每批之間間隔幾秒（預設 2）")
    parser.add_argument("--dry-run", action="store_true", help="只顯示數量，不呼叫 API")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        pending = count_pending_embeddings(db)
        chunks = estimate_chunks(db) if args.dry_run else 0
    finally:
        db.close()

    if args.dry_run:
        # 用「段落數」估算，不是「文章數」：
        # 一篇長文會切成好幾段，照文章數算會嚴重低估要打幾次 API，
        # 而 --dry-run 存在的意義就是先看清楚要花多少額度。
        logger.info(
            "尚未產生向量：%d 篇，約 %d 段，需要約 %d 次 API 呼叫（不會實際呼叫）",
            pending,
            chunks,
            -(-chunks // EMBED_BATCH_SIZE),
        )
        return

    started = time.monotonic()
    created = backfill(args.limit, args.pause)
    logger.info("完成：共產生 %d 筆向量，耗時 %.1f 分鐘", created, (time.monotonic() - started) / 60)


if __name__ == "__main__":
    main()
