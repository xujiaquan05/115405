"""從資料庫取出海報要用的統計，存成 data.json。

需用 backend/venv 執行（要連資料庫與 jieba）：
    cd backend
    venv\\Scripts\\python.exe ..\\output\\poster-trio\\data.py

海報上的每個數字都從這份檔案來，重跑一次就能更新到最新資料。
"""
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.services import beauty_lexicon as lexicon  # noqa: E402
from app.services.keyword_extractor import CONTENT_CHARS_FOR_DF, _tokens_in  # noqa: E402

OUT = Path(__file__).parent / "data.json"

# 「療程」相關的詞庫分組，用來做療程熱度排行（與保養、彩妝分開，避免被日常保養詞淹沒）。
TREATMENT_WORDS = (lexicon.INJECTION | lexicon.DEVICE | lexicon.SURGERY) - {"填充", "脂肪", "膠原", "膠原蛋白", "手術", "術後", "麻醉", "恢復期", "疤痕", "緊緻", "拉提", "探頭", "發數", "除皺"}

GROUPS = {
    "保養": lexicon.SKINCARE,
    "彩妝": lexicon.MAKEUP,
    "療程": lexicon.INJECTION | lexicon.DEVICE | lexicon.SURGERY | lexicon.DENTAL,
    "肌膚": lexicon.CONCERN | lexicon.SKIN,
    "醫療": lexicon.CLINIC,
}


def group_of(word: str) -> str:
    for name, words in GROUPS.items():
        if word in words:
            return name
    return "其他"


def nest(rows) -> dict:
    out: dict = {}
    for platform, sentiment, n in rows:
        out.setdefault(platform, {})[sentiment] = n
    return out


def main() -> None:
    with SessionLocal() as db:
        q = lambda sql: db.execute(text(sql)).all()  # noqa: E731
        articles = q("select count(*) from articles")[0][0]
        comments = q("select count(*) from comments")[0][0]
        chunks = q("select count(*) from article_chunks")[0][0]
        boards = q("select count(distinct board_id) from articles")[0][0]
        platforms = dict(q(
            "select p.name, count(*) from articles a join boards b on a.board_id=b.id "
            "join platforms p on b.platform_id=p.id group by p.name"
        ))
        sentiment = {k or "none": v for k, v in q("select sentiment, count(*) from articles group by 1")}
        monthly = q(
            "select to_char(published_at,'YYYY-MM'), count(*) from articles "
            "where published_at >= '2025-10-01' and published_at < '2026-10-01' group by 1 order by 1"
        )
        rows = q("select title, content from articles")
        # 各平台主文與留言的情緒分布（只算已判讀的三類）
        platform_sentiment = q(
            "select p.name, a.sentiment, count(*) from articles a join boards b on a.board_id=b.id "
            "join platforms p on b.platform_id=p.id where a.sentiment in ('positive','neutral','negative') group by 1,2"
        )
        comment_sentiment = q(
            "select p.name, c.sentiment, count(*) from comments c join articles a on c.article_id=a.id "
            "join boards b on a.board_id=b.id join platforms p on b.platform_id=p.id "
            "where c.sentiment in ('positive','neutral','negative') group by 1,2"
        )
        tables = q("select count(*) from information_schema.tables where table_schema='public' and table_name<>'alembic_version'")[0][0]
        plans = q("select count(*) from plans")[0][0]

    frequency: Counter[str] = Counter()
    for title, content in rows:
        frequency.update(_tokens_in(f"{title or ''} {(content or '')[:CONTENT_CHARS_FOR_DF]}"))

    data = {
        "as_of": date.today().isoformat(),
        "articles": articles,
        "comments": comments,
        "chunks": chunks,
        "boards": boards,
        "platforms": platforms,
        "sentiment": sentiment,
        "monthly": [list(row) for row in monthly],
        "platform_sentiment": nest(platform_sentiment),
        "comment_sentiment": nest(comment_sentiment),
        "tables": tables,
        "plans": plans,
        "top_terms": [(w, n, group_of(w)) for w, n in frequency.most_common(22)],
        "top_treatments": [(w, n) for w, n in frequency.most_common() if w in TREATMENT_WORDS][:8],
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
