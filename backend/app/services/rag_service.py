# backend/app/services/rag_service.py

import json
import re
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.core.time_utils import taiwan_now
from app.models.database_models import Article
from app.services.article_compressor import clean_text, compress_articles_for_llm
from app.services.llm_client import generate_json_response


DEFAULT_KEYWORDS = [
    "玻尿酸",
    "肉毒",
    "雷射",
    "音波",
    "電波",
    "隆鼻",
    "抽脂",
    "雙眼皮",
    "醫美",
    "診所",
    "副作用",
    "價格",
]

def _safe_json(raw_text: str, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return fallback


def _fallback_intent(question: str) -> dict[str, Any]:
    keywords = [keyword for keyword in DEFAULT_KEYWORDS if keyword in question]

    if not keywords:
        cleaned_question = re.sub(r"[？?。！!，,、]", " ", question)
        keywords = [part.strip() for part in cleaned_question.split() if part.strip()]

    sentiment = "all"
    if any(word in question for word in ["負評", "負面", "抱怨", "失敗", "不好"]):
        sentiment = "negative"
    elif any(word in question for word in ["好評", "正面", "推薦", "滿意"]):
        sentiment = "positive"

    days = 30
    if "一週" in question or "7天" in question or "七天" in question:
        days = 7
    elif "三個月" in question or "90天" in question:
        days = 90

    question_type = "opinion"
    if any(word in question for word in ["趨勢", "變化", "最近"]):
        question_type = "trend"
    elif any(word in question for word in ["多少", "幾篇", "數量"]):
        question_type = "count"
    elif any(word in question for word in ["比較", "競品", "對比"]):
        question_type = "comparison"

    return {
        "keywords": keywords[:3] or [question[:30]],
        "sentiment": sentiment,
        "days": days,
        "question_type": question_type,
    }


def parse_question_intent(question: str) -> dict[str, Any]:
    prompt = f"""
你是醫美輿情系統的查詢意圖解析器。
請把使用者問題轉成 JSON，不要輸出 markdown 或其他文字。

JSON 格式：
{{
  "keywords": ["關鍵字1", "關鍵字2"],
  "sentiment": "positive / negative / all",
  "days": 30,
  "question_type": "opinion / trend / count / comparison"
}}

規則：
- keywords 必須是適合查詢資料庫的短詞。
- days 只能是 7, 30, 90, 180 其中一個；無法判斷就用 30。
- sentiment 無法判斷就用 all。

使用者問題：{question}
"""

    fallback = _fallback_intent(question)

    try:
        parsed = _safe_json(generate_json_response(prompt), fallback)
    except Exception:
        return fallback

    keywords = parsed.get("keywords") or fallback["keywords"]
    if isinstance(keywords, str):
        keywords = [keywords]

    return {
        "keywords": [str(keyword).strip() for keyword in keywords if str(keyword).strip()][:5]
        or fallback["keywords"],
        "sentiment": parsed.get("sentiment") if parsed.get("sentiment") in {"positive", "negative", "all"} else fallback["sentiment"],
        "days": parsed.get("days") if parsed.get("days") in {7, 30, 90, 180} else fallback["days"],
        "question_type": parsed.get("question_type") if parsed.get("question_type") in {"opinion", "trend", "count", "comparison"} else fallback["question_type"],
    }


def retrieve_articles(
    db: Session,
    intent: dict[str, Any],
    limit: int = 12,
) -> list[Article]:
    end_date = taiwan_now()
    start_date = end_date - timedelta(days=intent.get("days", 30))

    keyword_filters = []
    for keyword in intent.get("keywords", []):
        keyword_like = f"%{keyword}%"
        keyword_filters.append(Article.title.ilike(keyword_like))
        keyword_filters.append(Article.content.ilike(keyword_like))

    query = (
        db.query(Article)
        .filter(or_(*keyword_filters))
        .filter(Article.published_at >= start_date)
        .filter(Article.published_at <= end_date)
    )

    # 說明：
    # 優先使用 LLM 評出的 sentiment；
    # 還沒評分的文章（NULL）暫時 fallback 回原本的 push_count 規則。
    sentiment = intent.get("sentiment", "all")
    if sentiment == "positive":
        query = query.filter(
            or_(
                Article.sentiment == "positive",
                and_(Article.sentiment.is_(None), Article.push_count >= 10),
            )
        )
    elif sentiment == "negative":
        query = query.filter(
            or_(
                Article.sentiment == "negative",
                and_(Article.sentiment.is_(None), Article.push_count < 0),
            )
        )

    if intent.get("question_type") == "trend":
        query = query.order_by(desc(Article.published_at))
    else:
        query = query.order_by(desc(Article.push_count), desc(Article.published_at))

    return query.limit(limit).all()


def serialize_sources(articles: list[Article], limit: int = 5) -> list[dict[str, Any]]:
    sources = []

    for article in articles[:limit]:
        sources.append({
            "id": article.id,
            "title": article.title,
            "board": article.board.name if article.board else "",
            "author": article.author.username if article.author else "unknown",
            "push_count": article.push_count or 0,
            "sentiment": article.sentiment,
            "published_at": article.published_at.strftime("%Y-%m-%d %H:%M:%S")
            if article.published_at else None,
            "url": article.url,
            "preview": clean_text(article.content or "")[:220],
        })

    return sources


def _fallback_answer(question: str, intent: dict[str, Any], articles: list[Article]) -> dict[str, Any]:
    titles = [article.title for article in articles[:3]]
    article_count = len(articles)
    keyword_text = "、".join(intent.get("keywords", []))

    return {
        "answer": f"根據目前資料庫找到的 {article_count} 篇相關文章，問題「{question}」主要和「{keyword_text}」相關。較值得注意的文章包括：" + "；".join(titles),
        "key_points": titles or ["目前可用資料不足，建議先執行爬蟲補充文章。"],
        "marketing_action": "先整理高互動文章中的疑慮與用詞，再調整社群文案與 FAQ。",
        "confidence": "medium" if article_count >= 5 else "low",
    }


def generate_rag_answer(
    question: str,
    intent: dict[str, Any],
    articles: list[Article],
) -> dict[str, Any]:
    if not articles:
        return {
            "answer": "目前資料庫中找不到足夠相關文章，請先執行爬蟲或換一個更明確的關鍵字。",
            "key_points": [],
            "marketing_action": "先補充資料，再進行判讀。",
            "confidence": "low",
        }

    articles_context = compress_articles_for_llm(
        articles,
        max_chars_per_article=300,
        max_total_chars=9000,
    )

    prompt = f"""
你是醫美品牌的輿情與行銷分析師。
請只根據提供的文章資料回答，不要自行發明資料。
如果資料不足，請誠實說明。

請只回傳 JSON，不要 markdown，不要額外說明。

JSON 格式：
{{
  "answer": "完整回答，請用繁體中文，具體說明觀察到的意見與原因",
  "key_points": ["重點摘要1", "重點摘要2", "重點摘要3"],
  "marketing_action": "給行銷人員的一句具體行動建議",
  "confidence": "high / medium / low"
}}

使用者問題：{question}
解析意圖：{json.dumps(intent, ensure_ascii=False)}

文章資料：
{articles_context}
"""

    fallback = _fallback_answer(question, intent, articles)

    try:
        return _safe_json(generate_json_response(prompt), fallback)
    except Exception:
        return fallback


def _dashboard_context_sources(dashboard_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not dashboard_context:
        return []

    hot_articles = dashboard_context.get("hot_articles") or []

    return [
        {
            "id": article.get("id"),
            "title": article.get("title"),
            "board": article.get("board"),
            "author": article.get("author"),
            "push_count": article.get("push_count", 0),
            "sentiment": article.get("sentiment"),
            "published_at": article.get("published_at"),
            "url": article.get("url"),
            "preview": article.get("preview", ""),
        }
        for article in hot_articles[:5]
        if isinstance(article, dict)
    ]


def generate_dashboard_context_answer(
    question: str,
    dashboard_context: dict[str, Any],
) -> dict[str, Any]:
    fallback = {
        "answer": "我會根據目前 Dashboard 的分析結果回答。這次分析可先從文章數、情緒比例、熱門文章與 LLM 洞察交叉判讀；若資料量不足，建議先回到 Dashboard 重新搜尋或補充爬蟲資料。",
        "key_points": [
            "回答優先引用目前 Dashboard 的 keyword、指標、情緒與熱門文章。",
            "如果 Dashboard 尚未載入，會以資料庫檢索結果輔助回答。",
        ],
        "marketing_action": "先確認 Dashboard 搜尋條件是否為最新，再依熱門文章與負面比例調整行銷訊息。",
        "confidence": "medium",
    }

    compact_context = {
        "keyword": dashboard_context.get("keyword"),
        "days": dashboard_context.get("days"),
        "overview": dashboard_context.get("overview"),
        "sentiment": dashboard_context.get("sentiment"),
        "keywords": dashboard_context.get("keywords"),
        "hot_articles": dashboard_context.get("hot_articles"),
        "insight": dashboard_context.get("insight"),
    }

    prompt = f"""
你是醫美時尚輿情分析系統的 AI 助理。
請「只根據下方 Dashboard 分析資料」回答使用者問題；如果資料不足，請明確說明不足之處。
回答要給行銷人員可直接採用的判讀，不要泛泛而談。

請只回傳 JSON，不要 markdown，不要額外說明。

JSON 格式：
{{
  "answer": "完整回答，使用繁體中文，必須明確連結目前 Dashboard 的指標、情緒、熱門文章或洞察",
  "key_points": ["重點1", "重點2", "重點3"],
  "marketing_action": "給行銷人員的一句具體行動建議",
  "confidence": "high / medium / low"
}}

使用者問題：{question}

Dashboard 分析資料：
{json.dumps(compact_context, ensure_ascii=False)}
"""

    try:
        return _safe_json(generate_json_response(prompt), fallback)
    except Exception:
        return fallback


def answer_question(
    db: Session,
    question: str,
    dashboard_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if dashboard_context:
        answer = generate_dashboard_context_answer(question, dashboard_context)

        return {
            "question": question,
            "intent": {
                "source": "dashboard_context",
                "keyword": dashboard_context.get("keyword"),
                "days": dashboard_context.get("days"),
            },
            "answer": answer.get("answer", ""),
            "key_points": answer.get("key_points", []),
            "marketing_action": answer.get("marketing_action", ""),
            "confidence": answer.get("confidence", "medium"),
            "sources": _dashboard_context_sources(dashboard_context),
        }

    intent = parse_question_intent(question)
    articles = retrieve_articles(db, intent)
    answer = generate_rag_answer(question, intent, articles)

    return {
        "question": question,
        "intent": intent,
        "answer": answer.get("answer", ""),
        "key_points": answer.get("key_points", []),
        "marketing_action": answer.get("marketing_action", ""),
        "confidence": answer.get("confidence", "low"),
        "sources": serialize_sources(articles),
    }
