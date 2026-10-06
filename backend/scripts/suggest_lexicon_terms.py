"""找出「資料裡常出現、但領域詞庫還沒收」的詞。

熱門話題只顯示 beauty_lexicon 裡的詞，所以新的療程、品牌或流行語
不會自己冒出來，要靠人補。這支腳本把候選詞撈出來排好，
人看過之後挑幾個加進 beauty_lexicon.py 即可——刻意不自動加入，
因為清單裡混進「昨天」「留言」這種詞，正是當初要解決的問題。

用法（在 backend 目錄下）：
    venv\\Scripts\\python.exe scripts\\suggest_lexicon_terms.py
    venv\\Scripts\\python.exe scripts\\suggest_lexicon_terms.py --sample 5000 --top 80
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jieba  # noqa: E402
from sqlalchemy import func  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.database_models import Article  # noqa: E402
from app.services.beauty_lexicon import BEAUTY_LEXICON  # noqa: E402
from app.services.keyword_extractor import CONTENT_CHARS_FOR_DF, STOPWORDS, _CJK_RE  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=3000, help="抽樣幾篇文章（預設 3000）")
    parser.add_argument("--top", type=int, default=60, help="列出前幾個候選詞（預設 60）")
    args = parser.parse_args()

    with SessionLocal() as db:
        rows = (
            db.query(Article.title, Article.content)
            .order_by(func.random())
            .limit(args.sample)
            .all()
        )

    appears_in: Counter[str] = Counter()
    for row in rows:
        text = f"{row.title or ''} {(row.content or '')[:CONTENT_CHARS_FOR_DF]}"
        words = {
            word for word in jieba.cut(text)
            if len(word) >= 2 and word not in STOPWORDS and _CJK_RE.search(word)
        }
        appears_in.update(words)

    candidates = [
        (word, count) for word, count in appears_in.most_common()
        if word not in BEAUTY_LEXICON
    ]

    print(f"抽樣 {len(rows)} 篇，詞庫目前 {len(BEAUTY_LEXICON)} 個詞")
    print(f"以下是出現最多、但不在詞庫裡的 {args.top} 個詞。")
    print("多數會是「還是」「最近」這類虛詞，請只挑真正的領域詞加入。\n")

    for word, count in candidates[:args.top]:
        print(f"  {word:<10} 出現於 {count:>5} 篇")


if __name__ == "__main__":
    main()
