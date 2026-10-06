"""抽出情緒標註評估用的樣本。

為什麼要分層抽樣而不是純隨機？
資料庫裡 neutral 約占六成，純隨機抽 100 篇大概只會抽到 7 篇 negative，
少到算不出可信的 negative 召回率。改成每類固定抽同樣篇數，
各類都有足夠樣本；回推整體正確率時再依母體比例加權。

輸出的檔案刻意不含 AI 標籤：標註者看得到答案就不算盲標。
對照表另存一份，評分時才合併。
"""
import csv
import json
import os
import pathlib
import random
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import create_engine, text

from app.services.article_compressor import clean_text
from app.services.article_service import COMMENT_SECTION_MARKER

SEED = 20261006          # 固定種子，重跑會得到同一批樣本
PER_CLASS = 34           # 三類各 34 篇 → 102 篇，取前 100
OUT = pathlib.Path(__file__).resolve().parents[2] / "docs/manual-work/sentiment-eval"
# 標註者看到的字數比評分器多（評分器只看 150+250），
# 才驗得出「截斷造成的誤判」。
LABEL_CHARS = 1200


def body(content: str | None) -> str:
    text_only = clean_text(content or "").split(COMMENT_SECTION_MARKER, 1)[0].strip()
    return text_only[:LABEL_CHARS]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    engine = create_engine(os.environ["DATABASE_URL"])
    rng = random.Random(SEED)
    picked = []

    with engine.connect() as conn:
        for label in ("positive", "neutral", "negative"):
            rows = conn.execute(text("""
                SELECT a.id, p.name AS platform, a.title, a.content, a.sentiment
                FROM articles a JOIN platforms p ON p.id = a.platform_id
                WHERE a.sentiment = :label
                  AND a.title IS NOT NULL AND length(trim(a.title)) > 0
                  AND a.content IS NOT NULL AND length(trim(a.content)) > 80
                ORDER BY a.id
            """), {"label": label}).fetchall()

            chosen = rng.sample(rows, min(PER_CLASS, len(rows)))
            picked.extend(chosen)
            print(f"  {label:9} co {len(rows):5} bai du dieu kien, lay {len(chosen)}")

    rng.shuffle(picked)                 # 打散，標註時看不出類別順序
    picked = picked[:100]

    with (OUT / "sample.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["序號", "文章id", "平台", "標題", "內文節錄", "你的標註"])
        for n, row in enumerate(picked, 1):
            writer.writerow([n, row.id, row.platform, clean_text(row.title), body(row.content), ""])

    (OUT / "answer_key.json").write_text(
        json.dumps({str(r.id): r.sentiment for r in picked}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    print(f"\nda ghi {len(picked)} bai vao {OUT}")
    print("  sample.csv     - phieu gan nhan (KHONG chua nhan AI)")
    print("  answer_key.json - nhan cua AI, de doi chieu sau")


if __name__ == "__main__":
    main()
