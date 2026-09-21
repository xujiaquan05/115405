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

import numpy as np

# 讓這個腳本不論從哪裡執行都能 import 到 app 套件。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.models.database_models import Article  # noqa: E402
from app.services.embedding_service import clean_text, embed_texts, rank_by_similarity  # noqa: E402
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

# 切段之前的作法：一篇文章只產生一個向量，文字取「標題 + 內文前 1000 字」。
# --deep 用它重現舊的表示法，量出切段到底帶來多少差別。
LEGACY_EMBED_CHARS = 1000

# --deep 的預設題。挑選原則是「答案埋在長文的中後段」：
# 一篇 6,774 字的體驗文在第 1,600 字左右才談到外泌體的植物來源，
# 舊作法取前 1,000 字根本看不到這一段。
DEFAULT_DEEP = (
    "外泌體是從哪裡來的，植物來源跟動物來源差在哪",
    ["外泌體", "植物來源"],
)


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


def run_deep(db, question: str, keywords: list[str], limit: int) -> None:
    """量出「切段」對長文的實際影響。

    做法是對照：同一篇長文，拿它「命中的那一段」與「舊作法的前 1000 字」
    分別跟問題算相似度，再看舊的分數會掉到第幾名。

    為什麼這個對照是公平的？
    其他上榜的文章若都短於 1000 字，它們的新舊表示法本來就是同一段文字，
    分數不會變，只有被截斷過的長文會動。輸出會一併印出各篇長度供檢查。
    """
    intent = {
        "keywords": keywords,
        "sentiment": "all",
        "days": ALL_TIME_DAYS,
        "question_type": "opinion",
        "platform": "all",
    }

    candidate_ids = [row[0] for row in apply_hard_filters(db.query(Article.id), intent).all()]
    ranked = rank_by_similarity(db, question, candidate_ids, limit=limit)

    if not ranked:
        print(f"\n問題：{question}\n  沒有結果（向量可能還沒產生）")
        return

    print(f"\n問題：{question}")
    print(f"  候選 {len(candidate_ids)} 篇，語意檢索前 {len(ranked)} 名：")

    long_article = None

    for position, (article_id, score, _chunk) in enumerate(ranked, start=1):
        article = db.get(Article, article_id)
        length = len(article.content or "")
        note = "← 舊作法會被截斷" if length > LEGACY_EMBED_CHARS else ""

        print(f"    {position}. {score:.4f}  {length:>5} 字  {(article.title or '')[:28]} {note}")

        if long_article is None and length > LEGACY_EMBED_CHARS:
            long_article = (position, article, score)

    if long_article is None:
        print("\n  前幾名都是短文，這題看不出切段的差別（短文的新舊表示法相同）。")
        return

    position, article, chunk_score = long_article
    legacy_text = f"{clean_text(article.title or '')}\n{clean_text(article.content or '')}"
    legacy_text = legacy_text[:LEGACY_EMBED_CHARS]

    question_vector = embed_texts([question], task_type="RETRIEVAL_QUERY")[0]
    legacy_vector = embed_texts([legacy_text])[0]

    legacy_score = float(
        np.dot(question_vector, legacy_vector)
        / (np.linalg.norm(question_vector) * np.linalg.norm(legacy_vector))
    )

    # 舊分數會排第幾名：數有多少篇分數比它高。
    would_rank = sum(1 for _id, score, _chunk in ranked if score > legacy_score) + 1
    dropped_out = would_rank > len(ranked)
    placement = f"掉出前 {len(ranked)} 名" if dropped_out else f"第 {would_rank} 名"

    print(f"\n  對照「{(article.title or '')[:28]}」（{len(article.content or '')} 字）：")
    print(f"    切段後，命中的那一段          ：{chunk_score:.4f}  → 第 {position} 名")
    print(f"    舊作法，前 {LEGACY_EMBED_CHARS} 字整篇一個向量：{legacy_score:.4f}  → {placement}")

    # 關鍵字有沒有落在前 1000 字，決定了這是「搆不到」還是「被稀釋」。
    hit_terms = [term for term in keywords if term in legacy_text]

    if hit_terms:
        print(
            f"\n    注意：「{'、'.join(hit_terms)}」本來就在前 {LEGACY_EMBED_CHARS} 字裡。"
            "\n          舊作法不是搆不到這個主題，而是一個向量要代表整篇、被稀釋掉了。"
        )


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
    parser.add_argument(
        "--deep",
        action="store_true",
        help="只跑長文對照：命中的那一段 vs 舊作法的前 1000 字",
    )
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
        if args.deep:
            question, keywords = DEFAULT_DEEP

            if args.question:
                question = args.question
                keywords = [args.keyword] if args.keyword else keywords

            print("=" * 72)
            print("長文對照：切段 vs 舊作法（整篇一個向量、只取前 1000 字）")
            print("=" * 72)
            run_deep(db, question, keywords, args.limit)
            return

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

        # 切段的好處只在長文上看得出來：短文的新舊表示法是同一段文字。
        # 上面幾組示範題命中的都是一兩百字的短文，完全看不出差別，
        # 所以另外用一題「答案埋在長文中後段」的問題來量。
        print("\n" + "=" * 72)
        print("長文對照：切段 vs 舊作法（整篇一個向量、只取前 1000 字）")
        print("=" * 72)
        run_deep(db, DEFAULT_DEEP[0], DEFAULT_DEEP[1], args.limit)
    finally:
        db.close()


if __name__ == "__main__":
    main()
