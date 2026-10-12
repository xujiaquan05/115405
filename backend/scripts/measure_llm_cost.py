"""估算每次 AI 呼叫的 token 用量與費用，作為營運成本試算的依據。

不呼叫 Gemini：用與正式流程相同的函式組出 prompt，量字數；
再以已存的分析結果量回覆長度。中文字以「1 字 ≈ 1 token」估算，
英文與數字其實更省，因此結果偏保守（高估）。

用法（在 backend 目錄下）：
    venv\\Scripts\\python.exe scripts\\measure_llm_cost.py
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, text  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.database_models import Article  # noqa: E402
from app.services.article_compressor import compress_articles_for_llm  # noqa: E402
from app.services.rag_service import _fallback_intent, retrieve_by_keyword  # noqa: E402
from app.services.sentiment_service import _build_batch_prompt, _build_comment_prompt  # noqa: E402

# 典型的使用者提問；意圖用規則版解析（不呼叫模型），檢索結果與正式流程的關鍵字路徑相同。
QUESTIONS = [
    "最近大家對玻尿酸的評價如何？",
    "皮秒雷射有哪些常見抱怨？",
    "音波拉皮和電波拉皮哪個討論度高？",
    "肉毒桿菌打完常見的副作用是什麼？",
    "近 30 天保濕產品的口碑重點？",
    "韓國醫美有什麼風險？",
]

# 規則版意圖解析 prompt 的固定部分（與 parse_question_intent 相同的說明文字長度）
INTENT_PROMPT_FIXED_CHARS = 420
INTENT_OUTPUT_CHARS = 150
RAG_PROMPT_FIXED_CHARS = 420


def main() -> None:
    report: dict = {}
    with SessionLocal() as db:
        qa_inputs = []
        for q in QUESTIONS:
            intent = _fallback_intent(q)
            articles = retrieve_by_keyword(db, intent, 12)
            context = compress_articles_for_llm(
                articles, max_chars_per_article=300, max_total_chars=13000, max_comment_chars=300
            )
            qa_inputs.append(RAG_PROMPT_FIXED_CHARS + len(q) + len(json.dumps(intent, ensure_ascii=False)) + len(context))

        # 已存的 LLM 回覆長度（儀表板洞察）作為輸出長度的參考
        outputs = [
            len(r[0] or "")
            for r in db.execute(text("select result_json::text from analysis_results order by id desc limit 50"))
        ]

        # 儀表板洞察：預設壓縮參數，取最新 12 篇做代表
        sample = db.query(Article).order_by(func.random()).limit(30).all()
        insight_input = 600 + len(compress_articles_for_llm(sample))

        batch = db.query(Article).filter(Article.sentiment.isnot(None)).order_by(func.random()).limit(20).all()
        sentiment_per_article = len(_build_batch_prompt(batch)) / len(batch)

        comments = db.execute(text("select id, content from comments order by random() limit 20")).all()

        class C:  # 只需要 id 與 content
            def __init__(self, row):
                self.id, self.content = row
        comment_per_item = len(_build_comment_prompt([C(r) for r in comments])) / len(comments)

        chunk_chars = db.execute(text("select avg(char_length(content)) from article_chunks")).scalar()
        chunks_per_article = db.execute(text(
            "select count(*)::float / nullif(count(distinct article_id),0) from article_chunks")).scalar()
        monthly = db.execute(text(
            "select count(*) from articles where published_at >= now() - interval '30 days'")).scalar()
        monthly_comments = db.execute(text(
            "select count(*) from comments c join articles a on c.article_id=a.id "
            "where a.published_at >= now() - interval '30 days'")).scalar()

    report = {
        "qa_input_chars": {"min": min(qa_inputs), "avg": round(statistics.mean(qa_inputs)), "max": max(qa_inputs)},
        "intent_input_chars": INTENT_PROMPT_FIXED_CHARS + 20,
        "intent_output_chars": INTENT_OUTPUT_CHARS,
        "stored_llm_output_chars": {
            "n": len(outputs),
            "avg": round(statistics.mean(outputs)) if outputs else None,
            "max": max(outputs) if outputs else None,
        },
        "insight_input_chars": insight_input,
        "sentiment_input_chars_per_article": round(sentiment_per_article),
        "comment_input_chars_per_item": round(comment_per_item),
        "chunk_chars_avg": round(chunk_chars or 0),
        "chunks_per_article": round(chunks_per_article or 0, 2),
        "articles_last_30_days": monthly,
        "comments_last_30_days": monthly_comments,
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
