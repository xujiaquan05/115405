# backend/app/services/sentiment_service.py

import json
import logging

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.database_models import Article
from app.services.article_compressor import clean_text
from app.services.llm_client import LLMServiceUnavailableError, generate_json_response


logger = logging.getLogger(__name__)

SENTIMENT_VALUES = {"positive", "neutral", "negative"}

# 說明：
# 每次呼叫 Gemini 一次評 20 篇，節省 API 額度。
# 每回合最多處理 200 篇 — 還沒評分的舊文章
# 會在之後的爬取回合中逐步補齊（backfill）。
BATCH_SIZE = 20
MAX_ARTICLES_PER_RUN = 200


def _build_batch_prompt(articles: list[Article]) -> str:
    items = [
        {
            "id": article.id,
            "title": clean_text(article.title or "")[:100],
            "content": clean_text(article.content or "")[:200],
        }
        for article in articles
    ]

    return f"""
你是醫美輿情系統的情緒分析器。
以下是 PTT 文章列表，請判斷每一篇「發文者的整體情緒傾向」：
- positive：明顯滿意、推薦、分享正面經驗
- negative：抱怨、後悔、副作用、糾紛、負面經驗
- neutral：提問、討論、資訊分享、看不出明顯情緒

請務必只回傳合法 JSON，不要 markdown 標記，不要額外說明文字。
JSON 格式：
{{"results": [{{"id": 123, "sentiment": "positive"}}]}}

文章列表：
{json.dumps(items, ensure_ascii=False)}
"""


def _parse_batch_response(raw_text: str) -> dict[int, str]:
    """
    說明：
    把 Gemini 回傳的 JSON 解析成 {article_id: sentiment}。
    不認識的 id 或不合法的標籤都會被忽略，
    該篇文章保持 sentiment = NULL，下次再重新評分。
    """

    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return {}

    results = parsed.get("results") if isinstance(parsed, dict) else None

    if not isinstance(results, list):
        return {}

    sentiments: dict[int, str] = {}

    for item in results:
        if not isinstance(item, dict):
            continue

        article_id = item.get("id")
        sentiment = str(item.get("sentiment", "")).strip().lower()

        if isinstance(article_id, int) and sentiment in SENTIMENT_VALUES:
            sentiments[article_id] = sentiment

    return sentiments


def classify_pending_sentiments(
    db: Session,
    max_articles: int = MAX_ARTICLES_PER_RUN,
    batch_size: int = BATCH_SIZE,
) -> int:
    """
    為還沒有 sentiment 的文章（sentiment IS NULL）評分，新文章優先。
    回傳成功評分的文章數。若 Gemini 忙碌就提早停止，
    剩下的文章等下次執行 — 不會把例外往外拋。
    """

    pending = (
        db.query(Article)
        .filter(Article.sentiment.is_(None))
        .order_by(desc(Article.published_at).nullslast())
        .limit(max_articles)
        .all()
    )

    if not pending:
        return 0

    updated_count = 0

    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]

        try:
            raw_response = generate_json_response(_build_batch_prompt(batch))
        except LLMServiceUnavailableError:
            logger.warning(
                "Gemini unavailable, stopped sentiment scoring after %s articles",
                updated_count,
            )
            break
        except Exception:
            logger.exception("Sentiment scoring failed, stopping this run")
            break

        sentiments = _parse_batch_response(raw_response)

        for article in batch:
            sentiment = sentiments.get(article.id)

            if sentiment:
                article.sentiment = sentiment
                updated_count += 1

        db.commit()

    return updated_count
