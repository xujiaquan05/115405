"""比較「關鍵字檢索」與「語意檢索」在實際資料上的差異。

做什麼用？
RAG 同時跑關鍵字（SQL ILIKE）與語意（向量餘弦相似度）兩種檢索再合併，
這支工具把兩邊的結果並排印出來，用來回答「語意檢索到底有沒有用」——
不是靠說的，是看它實際多找到哪些文章。

用法（在 backend 目錄下）：
    venv\\Scripts\\python.exe scripts\\compare_retrieval.py
    venv\\Scripts\\python.exe scripts\\compare_retrieval.py --question "音波拉皮術後多久消腫"
    venv\\Scripts\\python.exe scripts\\compare_retrieval.py --keyword 除皺針 --question "除皺針的副作用"

兩種模式：
- 給 --keyword：跳過意圖解析，直接指定關鍵字做對照實驗。
  想示範「這個詞資料庫裡一次都沒出現過」時用這個，變因才單純。
- 不給 --keyword：走完整流程（Gemini 解析意圖 → 兩種檢索 → RRF 合併），
  看到的就是使用者提問時真正發生的事。

會呼叫 Gemini（每題一次向量、完整流程再多一次意圖解析），消耗少量額度。
"""

import argparse
import sys
import time
from pathlib import Path

# 讓這個腳本不論從哪裡執行都能 import 到 app 套件。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.models.database_models import Article  # noqa: E402
from app.services.rag_service import (  # noqa: E402
    apply_hard_filters,
    parse_question_intent,
    retrieve_articles,
    retrieve_by_keyword,
    retrieve_by_vector,
)

# 預設示範題。挑選原則是「問法與文章用詞不同」，
# 這正是關鍵字檢索的死角：
# - 除皺針：資料庫裡一次都沒出現，但有 139 篇在講肉毒，指的是同一件事。
# - 填充物：只有 8 篇，寫「玻尿酸」的卻有 293 篇。
DEFAULT_CONTROLLED = [
    ("除皺針", "除皺針打了會有什麼副作用"),
    ("填充物", "打完填充物臉會腫多久"),
]

DEFAULT_QUESTIONS = [
    "臉部鬆弛想做拉提，大家推薦哪種療程",
    "音波拉皮術後多久才會消腫",
]


# 全庫掃描用的天數：大到足以涵蓋所有文章。
ALL_TIME_DAYS = 9999


def timed(function, *args, **kwargs):
    """執行並回傳 (結果, 毫秒)。用來看時間實際花在哪裡。"""
    started = time.perf_counter()
    result = function(*args, **kwargs)

    return result, (time.perf_counter() - started) * 1000


def show(label: str, articles: list, limit: int, elapsed_ms: float | None = None) -> None:
    timing = f"（{elapsed_ms:.0f}ms）" if elapsed_ms is not None else ""
    print(f"  {label}：{len(articles)} 篇{timing}")

    for article in articles[:limit]:
        platform = article.platform.name if article.platform else "?"
        print(f"      [{platform}] {(article.title or '')[:46]}")


def run_controlled(db, keyword: str, question: str, limit: int, days: int = 180) -> None:
    """對照實驗：固定關鍵字，只比較兩種檢索本身的差別。"""
    intent = {
        "keywords": [keyword],
        "sentiment": "all",
        "days": days,
        "question_type": "opinion",
        "platform": "all",
    }

    candidates = apply_hard_filters(db.query(Article.id), intent).count()

    print(f"\n問題：{question}（關鍵字「{keyword}」，{days} 天內共 {candidates} 篇候選）")

    keyword_hits, keyword_ms = timed(retrieve_by_keyword, db, intent)
    vector_hits, vector_ms = timed(retrieve_by_vector, db, question, intent)

    show("關鍵字檢索", keyword_hits, limit, keyword_ms)
    show("語意檢索　", vector_hits, limit, vector_ms)


def run_full(db, question: str, limit: int) -> None:
    """完整流程：意圖解析 → 兩種檢索 → RRF 合併。"""
    intent = parse_question_intent(question)

    keyword_hits = retrieve_by_keyword(db, intent)
    vector_hits = retrieve_by_vector(db, question, intent)
    fused = retrieve_articles(db, intent, question=question)

    keyword_ids = {article.id for article in keyword_hits}
    vector_ids = {article.id for article in vector_hits}

    print(f"\n問題：{question}")
    print(
        f"  解析關鍵字：{intent['keywords']}"
        f"｜天數 {intent['days']}｜平台 {intent['platform']}"
    )
    show("關鍵字檢索", keyword_hits, limit)
    show("語意檢索　", vector_hits, limit)
    print(
        f"  兩者重疊：{len(keyword_ids & vector_ids)} 篇"
        f"｜語意獨有：{len(vector_ids - keyword_ids)} 篇"
        f"｜關鍵字獨有：{len(keyword_ids - vector_ids)} 篇"
    )
    show("合併後　　", fused, limit)


def main() -> None:
    parser = argparse.ArgumentParser(description="比較關鍵字檢索與語意檢索")
    parser.add_argument("--question", help="要測試的問題（預設跑內建示範題）")
    parser.add_argument("--keyword", help="固定關鍵字做對照實驗，跳過意圖解析")
    parser.add_argument("--limit", type=int, default=5, help="每組印出幾篇（預設 5）")
    parser.add_argument(
        "--days",
        type=int,
        default=180,
        help=f"對照實驗的時間範圍，用 {ALL_TIME_DAYS} 代表全庫（預設 180）",
    )
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.keyword:
            if not args.question:
                parser.error("--keyword 需要搭配 --question")

            print("=" * 72)
            print("對照實驗：固定關鍵字")
            print("=" * 72)
            run_controlled(db, args.keyword, args.question, args.limit, args.days)
            return

        if args.question:
            print("=" * 72)
            print("完整流程")
            print("=" * 72)
            run_full(db, args.question, args.limit)
            return

        print("=" * 72)
        print("對照實驗：關鍵字完全沒有字面命中")
        print("=" * 72)
        for keyword, question in DEFAULT_CONTROLLED:
            run_controlled(db, keyword, question, args.limit, args.days)

        # 全庫掃描：不限時間，語意檢索要比對資料庫裡每一篇文章的向量。
        # 這一段看的是「資料量長大會不會拖垮查詢」。
        # 實測近一萬篇的精確餘弦計算只要幾十毫秒，時間幾乎都花在
        # 呼叫 API 把問題轉成向量，而那一段與資料量多寡無關——
        # 也就是說，在這個規模下換成近似索引（pgvector）並不會比較快。
        print("\n" + "=" * 72)
        print("全庫掃描：不限時間範圍")
        print("=" * 72)
        for keyword, question in DEFAULT_CONTROLLED:
            run_controlled(db, keyword, question, args.limit, ALL_TIME_DAYS)

        print("\n" + "=" * 72)
        print("完整流程：意圖解析後混合檢索")
        print("=" * 72)
        for question in DEFAULT_QUESTIONS:
            run_full(db, question, args.limit)
    finally:
        db.close()


if __name__ == "__main__":
    main()
