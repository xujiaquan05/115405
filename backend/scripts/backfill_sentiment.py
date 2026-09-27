"""一次性工具：為資料庫裡還沒有情緒評分的舊文章與留言補上評分。

為什麼需要？
sentiment_service 只在每次爬取後評分，而且一次最多 200 篇（留言同樣 200 則），
所以一次爬進大量資料時評分會嚴重落後。實測修好 PTT 推文擷取後，
單次爬取就新增 3,119 則留言，而一天只跑一輪排程 —— 照這個速度要二十天才追得上。

儀表板遇到未評分的文章會退回用 push_count 推估，把大量文章歸成「中性」；
未評分的留言則完全不列入留言情緒分析。把舊資料補齊，數字才名實相符。

用法（在 backend 目錄下）：
    venv\\Scripts\\python.exe scripts\\backfill_sentiment.py --dry-run
    venv\\Scripts\\python.exe scripts\\backfill_sentiment.py
    venv\\Scripts\\python.exe scripts\\backfill_sentiment.py --target comments
    venv\\Scripts\\python.exe scripts\\backfill_sentiment.py --limit 500

注意：
- 會實際呼叫 Gemini API 並消耗額度，執行前請先用 --dry-run 確認數量。
- 每批 20 筆送一次 API，批次之間預設間隔 4 秒，避免觸發每分鐘請求上限。
- 每批評分完就 commit，中途用 Ctrl+C 停掉也不會丟失已完成的部分，
  下次再執行會從剩下的接著跑。
"""

import argparse
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# 讓這個腳本不論從哪裡執行都能 import 到 app 套件。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.models.database_models import Article, Comment  # noqa: E402
from app.services.sentiment_service import (  # noqa: E402
    BATCH_SIZE,
    classify_pending_comments,
    classify_pending_sentiments,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s | %(message)s")
logger = logging.getLogger("backfill_sentiment")

# 送出請求被拒（429 / 5xx）之後等多久再試。
RETRY_WAIT_SECONDS = 60

# 連續幾輪「待評分數量都沒有減少」就放棄。
# 看數量而不是看評分成功數：被安全機制擋下的文章會被標記起來，
# 這種批次評分數是 0 但確實有進展，不該被當成卡住。
MAX_STALLED_ROUNDS = 3


@dataclass(frozen=True)
class Target:
    """一種要補評分的對象。

    文章與留言的補跑流程完全一樣——分批、偵測卡住、可中斷續跑——
    差別只在「數哪張表」與「呼叫哪個評分函式」。
    把這兩件事抽成參數，補跑的邏輯就只需要維護一份。
    """

    key: str
    label: str
    unit: str
    count: Callable
    classify: Callable


def _count_pending_articles(db) -> int:
    return db.query(Article).filter(Article.sentiment.is_(None)).count()


def _count_pending_comments(db) -> int:
    return db.query(Comment).filter(Comment.sentiment.is_(None)).count()


ARTICLES = Target(
    key="articles",
    label="文章",
    unit="篇",
    count=_count_pending_articles,
    classify=lambda db: classify_pending_sentiments(
        db, max_articles=BATCH_SIZE, batch_size=BATCH_SIZE
    ),
)

COMMENTS = Target(
    key="comments",
    label="留言",
    unit="則",
    count=_count_pending_comments,
    classify=lambda db: classify_pending_comments(
        db, max_comments=BATCH_SIZE, batch_size=BATCH_SIZE
    ),
)

TARGETS = {ARTICLES.key: [ARTICLES], COMMENTS.key: [COMMENTS], "all": [ARTICLES, COMMENTS]}


def backfill(target: Target, limit: int | None, pause: float) -> int:
    """逐批補評分，回傳成功評分的筆數。"""

    db = SessionLocal()

    try:
        pending = target.count(db)
        logger.info("尚未評分的%s：%d %s", target.label, pending, target.unit)

        scored_total = 0
        stalled_rounds = 0

        while True:
            if limit is not None and scored_total >= limit:
                logger.info("已達 --limit %d，停止。", limit)
                break

            before = target.count(db)

            if before == 0:
                logger.info("所有%s都已評分。", target.label)
                break

            try:
                # 一次只送一批，節奏才握在自己手上
                # （classify_* 內部會連續送完上限數量，
                #   一口氣 10 批容易撞到每分鐘請求上限）。
                scored = target.classify(db)
            except Exception:
                logger.exception("這一批失敗，等 %d 秒後再試", RETRY_WAIT_SECONDS)
                time.sleep(RETRY_WAIT_SECONDS)
                continue

            remaining = target.count(db)

            if remaining >= before:
                stalled_rounds += 1
                logger.warning(
                    "這一批待評分數量沒有減少（第 %d/%d 次），可能是額度用完",
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
            blocked = (before - remaining) - scored
            logger.info(
                "本批 +%d%s｜累計 %d｜剩餘 %d",
                scored,
                f"（被擋 {blocked}）" if blocked else "",
                scored_total,
                remaining,
            )

            if remaining:
                time.sleep(pause)

        return scored_total
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="為舊文章與留言補上 Gemini 情緒評分")
    parser.add_argument(
        "--target",
        choices=sorted(TARGETS),
        default="all",
        help="要補評分的對象（預設 all：文章與留言都補）",
    )
    parser.add_argument("--limit", type=int, default=None, help="每種對象最多評分幾筆（預設：全部）")
    parser.add_argument("--pause", type=float, default=4.0, help="每批之間間隔幾秒（預設 4）")
    parser.add_argument("--dry-run", action="store_true", help="只顯示數量，不呼叫 Gemini")
    args = parser.parse_args()

    targets = TARGETS[args.target]

    if args.dry_run:
        db = SessionLocal()
        try:
            for target in targets:
                pending = target.count(db)
                logger.info(
                    "尚未評分的%s：%d %s，需要約 %d 次 API 呼叫（不會實際呼叫）",
                    target.label,
                    pending,
                    target.unit,
                    -(-pending // BATCH_SIZE),
                )
        finally:
            db.close()
        return

    started = time.monotonic()
    total = 0

    for target in targets:
        total += backfill(target, args.limit, args.pause)

    logger.info("完成：共評分 %d 筆，耗時 %.1f 分鐘", total, (time.monotonic() - started) / 60)


if __name__ == "__main__":
    main()
