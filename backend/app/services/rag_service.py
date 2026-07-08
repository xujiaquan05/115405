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

JSON_RULE = "請務必只回傳合法 JSON，不要加入 markdown 標記，不要加入任何額外說明文字。"

QA_ANSWER_GUIDELINES = """
【AI 問答回答原則｜務必全部遵守】
1. 專注問題：只回答使用者這次提出的問題，不要延伸到無關主題，也不要把 Dashboard 所有資料重新摘要一遍。
2. 依據資料：只能根據提供的 Dashboard 分析資料或文章資料回答；資料沒有出現的數字、原因、療效、品牌表現，禁止自行推測或杜撰。
3. 專業但白話：用醫美輿情與行銷分析師的角度回答，但句子要自然、簡單、好懂，避免堆疊術語。
4. 條理清楚：回答要有明確判斷、原因與下一步；每一點都要讓使用者知道「這代表什麼、為什麼重要、可以怎麼做」。
5. 資料不足要明說：如果資料不足以回答，請直接說明缺少哪一類資料，並給出下一步應該補查或重新分析的方向。
6. 醫美法遵：醫美屬醫療廣告管制領域，回答只能談輿情、行銷、溝通與內容策略，不得出現療效保證或誇大宣傳。
7. 回答深度：除非問題只問數字，answer 請寫成 2–4 個自然段，包含「直接結論、資料依據、專業解讀、可採取方向」。
8. 可以給判讀意見：可以加入少量專業觀點，但必須明確建立在提供資料上；請使用「從目前資料看起來」「這代表」「建議優先」等保守措辭。
"""


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
你是醫美時尚輿情分析系統的 AI 問答助理，也是一位醫美輿情與行銷分析師。
你的任務不是重新做完整報告，而是「精準回答使用者問題」。
{QA_ANSWER_GUIDELINES}
{JSON_RULE}

JSON 格式：
{{
  "answer": "針對使用者問題的完整回答，使用繁體中文；除非問題只問數字，請寫 2–4 個自然段，語氣專業、自然、容易理解，並明確指出判斷依據與專業解讀",
  "key_points": [
    "只列出和問題直接相關的重點 1",
    "只列出和問題直接相關的重點 2",
    "只列出和問題直接相關的重點 3",
    "若資料足夠，可補充第 4 個重點"
  ],
  "marketing_action": "若問題和行銷決策有關，給一個可執行下一步；若資料不足，請說明應先補查什麼",
  "confidence": "high / medium / low"
}}

使用者問題：{question}
解析意圖：{json.dumps(intent, ensure_ascii=False)}

可用文章資料：
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
你是醫美時尚輿情分析系統的 AI 問答助理，也是一位醫美輿情與行銷分析師。
你的任務不是重新做完整 Dashboard 報告，而是「精準回答使用者問題」。
請優先使用下方 Dashboard 分析資料；若資料不足，請明確說明不足之處，不要自行補空白。
{QA_ANSWER_GUIDELINES}
{JSON_RULE}

JSON 格式：
{{
  "answer": "針對使用者問題的完整回答，使用繁體中文；除非問題只問數字，請寫 2–4 個自然段，語氣專業、自然、容易理解，並明確連結目前 Dashboard 的相關資料與專業解讀",
  "key_points": [
    "只列出和問題直接相關的重點 1",
    "只列出和問題直接相關的重點 2",
    "只列出和問題直接相關的重點 3",
    "若資料足夠，可補充第 4 個重點"
  ],
  "marketing_action": "若問題和行銷決策有關，給一個可執行下一步；若資料不足，請說明應先補查什麼",
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
