"""備份或還原 articles / comments 的情緒標籤。

重新評分整個資料庫之前一定要先備份：評分會覆蓋既有標籤，
出了問題沒有備份就只能整批重跑，而重跑同樣要花 API 額度。

用法（在 backend 目錄下）：
    venv\\Scripts\\python.exe scripts\\sentiment_labels_backup.py save
    venv\\Scripts\\python.exe scripts\\sentiment_labels_backup.py restore logs\\sentiment-backup-20261006-2141.csv
    venv\\Scripts\\python.exe scripts\\sentiment_labels_backup.py clear --target articles

clear 會把標籤設成 NULL，讓 backfill_sentiment.py 重新評分；
它只動已經有標籤的列，blocked 的列預設保留
（那些是被內容安全機制擋下的，清掉只會讓它們再被挑中、再被擋一次）。
"""
import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402

TABLES = ("articles", "comments")
BACKEND = Path(__file__).resolve().parent.parent


def save() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out = BACKEND / "logs" / f"sentiment-backup-{stamp}.csv"
    out.parent.mkdir(exist_ok=True)

    rows = 0
    with SessionLocal() as db, out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["table", "id", "sentiment"])
        for table in TABLES:
            for row in db.execute(text(f"SELECT id, sentiment FROM {table} ORDER BY id")):
                writer.writerow([table, row[0], row[1] or ""])
                rows += 1

    print(f"已備份 {rows} 列到 {out}")
    return out


def restore(path: Path) -> None:
    by_table: dict[str, list[tuple[int, str | None]]] = {t: [] for t in TABLES}
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["table"] in by_table:
                by_table[row["table"]].append((int(row["id"]), row["sentiment"] or None))

    with SessionLocal() as db:
        for table, pairs in by_table.items():
            for start in range(0, len(pairs), 500):
                db.execute(
                    text(f"UPDATE {table} SET sentiment = :s WHERE id = :i"),
                    [{"i": i, "s": s} for i, s in pairs[start:start + 500]],
                )
                db.commit()
            print(f"  {table}：還原 {len(pairs)} 列")


def clear(target: str, keep_blocked: bool) -> None:
    tables = TABLES if target == "all" else (target,)

    with SessionLocal() as db:
        for table in tables:
            before = Counter(
                row[0] or "(未評分)"
                for row in db.execute(text(f"SELECT sentiment FROM {table}"))
            )
            condition = "sentiment IS NOT NULL"
            if keep_blocked:
                condition += " AND sentiment <> 'blocked'"

            result = db.execute(text(f"UPDATE {table} SET sentiment = NULL WHERE {condition}"))
            db.commit()
            print(f"  {table}：清掉 {result.rowcount} 列（原本 {dict(before)}）")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("save")

    restore_parser = sub.add_parser("restore")
    restore_parser.add_argument("path")

    clear_parser = sub.add_parser("clear")
    clear_parser.add_argument("--target", choices=["articles", "comments", "all"], default="all")
    clear_parser.add_argument(
        "--include-blocked", action="store_true",
        help="連 blocked 的列也清掉（預設保留，避免又被擋一次白花額度）",
    )

    args = parser.parse_args()

    if args.command == "save":
        save()
    elif args.command == "restore":
        restore(Path(args.path))
    else:
        clear(args.target, keep_blocked=not args.include_blocked)


if __name__ == "__main__":
    main()
