"""一次性工具：為資料庫裡還沒有情緒評分的舊文章補上評分。

為什麼需要？
sentiment_service 只在每次爬取後評分，而且一次最多 200 篇，
所以早期累積的文章始終是 sentiment NULL。儀表板遇到 NULL 會退回用
push_count 推估，把大量文章歸成「中性」——圖表看起來像情緒分佈，
實際上有相當比例只是推文數。把舊文章補評分才能讓圖表名實相符。

用法（在 backend 目錄下）：
    venv\\Scripts\\python.exe scripts\\backfill_sentiment.py --dry-run
    venv\\Scripts\\python.exe scripts\\backfill_sentiment.py
    venv\\Scripts\\python.exe scripts\\backfill_sentiment.py --limit 500

注意：
- 會實際呼叫 Gemini API 並消耗額度，執行前請先用 --dry-run 確認數量。
- 每批 20 篇送一次 API，批次之間預設間隔 4 秒，避免觸發每分鐘請求上限。
- 每批評分完就 commit，中途用 Ctrl+C 停掉也不會丟失已完成的部分，
  下次再執行會從剩下的文章接著跑。
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# 讓這個腳本不論從哪裡執行都能 import 到 app 套件。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.models.database_models import Article  # noqa: E402
from app.services.sentiment_service import BATCH_SIZE, classify_pending_sentiments  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s | %(message)s")
logger = logging.getLogger("backfill_sentiment")

# 送出請求被拒（429 / 5xx）之後等多久再試。
RETRY_WAIT_SECONDS = 60

# 連續幾輪都沒有任何文章被評分就放棄。
# 防止「Gemini 一直回不出這幾篇的結果」變成無限迴圈重複燒額度。
MAX_STALLED_ROUNDS = 3


def count_pending(db) -> int:
    return db.query(Article).filter(Article.sentiment.is_(None)).count()


def backfill(limit: int | None, pause: float) -> int:
    """逐批補評分，回傳成功評分的文章數。"""

    db = SessionLocal()

    try:
        pending = count_pending(db)
        logger.info("尚未評分的文章：%d 篇（約 %d 批）", pending, -(-pending // BATCH_SIZE))

        scored_total = 0
        stalled_rounds = 0

        while True:
            if limit is not None and scored_total >= limit:
                logger.info("已達 --limit %d，停止。", limit)
                break

            if count_pending(db) == 0:
                logger.info("所有文章都已評分。")
                break

            try:
                # 一次只送一批，節奏才握在自己手上
                # （classify_pending_sentiments 內部會連續送完 max_articles，
                #   一口氣 10 批容易撞到每分鐘請求上限）。
                scored = classify_pending_sentiments(
                    db, max_articles=BATCH_SIZE, batch_size=BATCH_SIZE
                )
            except Exception:
                logger.exception("這一批失敗，等 %d 秒後再試", RETRY_WAIT_SECONDS)
                time.sleep(RETRY_WAIT_SECONDS)
                continue

            if scored == 0:
                stalled_rounds += 1
                logger.warning(
                    "這一批沒有任何文章被評分（第 %d/%d 次），可能是額度用完或回應格式有問題",
                    stalled_rounds,
                    MAX_STALLED_ROUNDS,
                )

                if stalled_rounds >= MAX_STALLED_ROUNDS:
                    logger.error("連續 %d 批都沒有進展，停止以免空轉消耗額度。", MAX_STALLED_ROUNDS)
                    break

                time.sleep(RETRY_WAIT_SECONDS)
                continue

            stalled_rounds = 0
            scored_total += scored
            remaining = count_pending(db)
            logger.info("本批 +%d｜累計 %d｜剩餘 %d", scored, scored_total, remaining)

            if remaining:
                time.sleep(pause)

        return scored_total
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="為舊文章補上 Gemini 情緒評分")
    parser.add_argument("--limit", type=int, default=None, help="最多評分幾篇（預設：全部）")
    parser.add_argument("--pause", type=float, default=4.0, help="每批之間間隔幾秒（預設 4）")
    parser.add_argument("--dry-run", action="store_true", help="只顯示數量，不呼叫 Gemini")
    args = parser.parse_args()

    if args.dry_run:
        db = SessionLocal()
        try:
            pending = count_pending(db)
            logger.info(
                "尚未評分：%d 篇，需要約 %d 次 API 呼叫（不會實際呼叫）",
                pending,
                -(-pending // BATCH_SIZE),
            )
        finally:
            db.close()
        return

    started = time.monotonic()
    scored = backfill(args.limit, args.pause)
    logger.info("完成：共評分 %d 篇，耗時 %.1f 分鐘", scored, (time.monotonic() - started) / 60)


if __name__ == "__main__":
    main()
