"""用目前的 prompt 重新評分評估樣本，不寫回資料庫。

用途是驗證 prompt 改動有沒有真的改善，改完先跑這支看分數，
確認有進步再決定要不要重跑全庫 backfill。
"""
import json
import pathlib
import sys

from dotenv import load_dotenv

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

from sqlalchemy import create_engine, text          # noqa: E402
from sqlalchemy.orm import Session                  # noqa: E402

from app.models.database_models import Article      # noqa: E402
from app.services.sentiment_service import (        # noqa: E402
    BATCH_SIZE,
    _build_batch_prompt,
    _parse_batch_response,
)
from app.services.llm_client import (  # noqa: E402
    CLASSIFY_TEMPERATURE,
    generate_json_response,
)

import os                                            # noqa: E402

EVAL = BACKEND.parent / "docs/manual-work/sentiment-eval"


def main(out_name: str = "rescored_labels.txt") -> None:
    ids = [int(i) for i in json.loads((EVAL / "answer_key.json").read_text(encoding="utf-8"))]
    engine = create_engine(os.environ["DATABASE_URL"])

    with Session(engine) as db:
        articles = db.query(Article).filter(Article.id.in_(ids)).all()
        by_id = {a.id: a for a in articles}
        ordered = [by_id[i] for i in ids if i in by_id]
        print(f"取回 {len(ordered)} 篇")

        results: dict[int, str] = {}
        for start in range(0, len(ordered), BATCH_SIZE):
            batch = ordered[start:start + BATCH_SIZE]
            prompt = _build_batch_prompt(batch)
            raw = generate_json_response(prompt, CLASSIFY_TEMPERATURE)
            parsed = _parse_batch_response(raw)
            results.update(parsed)
            print(f"  第 {start // BATCH_SIZE + 1} 批：送出 {len(batch)} 篇，取回 {len(parsed)} 筆")

            if not parsed:
                # 解析不出東西時要看得到原始回應，否則只會知道「這批沒結果」。
                print(f"    回應長度：{len(raw) if raw else 'None'}")
                print(f"    開頭：{(raw or '')[:300]!r}")
                print(f"    結尾：{(raw or '')[-200:]!r}")

    missing = [i for i in ids if i not in results]
    if missing:
        print(f"沒有取得結果的 id：{missing}")

    lines = [f"{i} {results[i]}" for i in ids if i in results]
    (EVAL / out_name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已寫入 {EVAL / out_name}（{len(lines)} 筆）")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "rescored_labels.txt")
