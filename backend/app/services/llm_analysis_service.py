# backend/app/services/llm_analysis_service.py

import hashlib
import json
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.database_models import AnalysisResult
from app.services.article_compressor import (
    get_related_articles,
    compress_articles_for_llm,
)
from app.services.llm_prompts import build_prompt
from app.services.llm_client import LLMServiceUnavailableError, generate_json_response


CACHE_HOURS = 6
# 2026-07-08：洞察分析提示詞還原為原始版本，
# 更新版本號讓帶有 5W2H1E 結構的舊 cache 全部失效。
PROMPT_CACHE_VERSION = "p20260708"


def build_cache_analysis_type(analysis_type: str, boards: list[str] | None = None) -> str:
    versioned_type = f"{analysis_type}:{PROMPT_CACHE_VERSION}"

    if not boards:
        return versioned_type[:50]

    boards_key = ",".join(sorted(boards))
    boards_hash = hashlib.sha1(boards_key.encode("utf-8")).hexdigest()[:12]

    return f"{versioned_type}:b{boards_hash}"[:50]


def get_cached_analysis(
    db: Session,
    keyword: str,
    analysis_type: str,
    days: int,
):
    """
    說明：
    檢查 keyword + analysis_type + days 是否已有 cache。

    如果有 cache 且尚未過期：
    - 回傳舊結果
    - 不呼叫 Gemini API

    如果沒有或已過期：
    - 回傳 None
    """

    now = datetime.utcnow()

    cached = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.keyword == keyword)
        .filter(AnalysisResult.analysis_type == analysis_type)
        .filter(AnalysisResult.days == days)
        .filter(AnalysisResult.expired_at > now)
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )

    return cached


def save_analysis_cache(
    db: Session,
    keyword: str,
    analysis_type: str,
    days: int,
    result_json: dict,
):
    """
    說明：
    把分析結果存入 database。

    expired_at = 現在 + 6 小時。
    這 6 小時內若 user 用相同條件再查詢，
    backend 會直接使用 cache，不再呼叫 Gemini。
    """

    expired_time = datetime.utcnow() + timedelta(hours=CACHE_HOURS)

    existing_cache = (
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.keyword == keyword,
            AnalysisResult.analysis_type == analysis_type,
        )
        .first()
    )

    if existing_cache:
        existing_cache.days = days
        existing_cache.result_json = result_json
        existing_cache.expired_at = expired_time
    else:
        cache = AnalysisResult(
            keyword=keyword,
            analysis_type=analysis_type,
            days=days,
            result_json=result_json,
            expired_at=expired_time,
        )
        db.add(cache)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()

def parse_llm_json(raw_text: str) -> dict:
    """
    說明：
    把 Gemini 回傳的文字轉成 Python dict。

    雖然已要求 JSON mode，仍加上 try/except，
    避免 LLM 回傳不合法格式時導致 server crash。
    """

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "summary": "LLM 回傳格式無法解析，請稍後重試。",
            "raw_response": raw_text,
        }


def analyze_keyword_with_llm(
    db: Session,
    keyword: str,
    analysis_type: str = "overview",
    days: int = 30,
    force_refresh: bool = False,
    boards: list[str] | None = None,
) -> dict:
    """
    說明：
    LLM 分析的主要函式。

    流程：
    1. 檢查 analysis_results 中的 cache
    2. 有 cache 就直接回傳
    3. 沒有 cache 就查詢 articles
    4. 壓縮文章
    5. 產生 prompt
    6. 呼叫 Gemini
    7. 解析 JSON
    8. 把結果存入 cache
    9. 回傳結果給 API
    """

    # force_refresh=False 時優先使用 cache；
    # force_refresh=True 時跳過 cache，重新呼叫 Gemini。
    cache_analysis_type = build_cache_analysis_type(analysis_type, boards)

    if not force_refresh:
        cached = get_cached_analysis(
            db=db,
            keyword=keyword,
            analysis_type=cache_analysis_type,
            days=days,
        )

        if cached:
            return {
                "cached": True,
                "keyword": keyword,
                "analysis_type": analysis_type,
                "days": days,
                "boards": boards or [],
                "data": cached.result_json,
            }

    # 從 articles 資料表取得相關文章。
    articles = get_related_articles(
        db=db,
        keyword=keyword,
        days=days,
        limit=30,
        boards=boards,
    )

    if not articles:
        return {
            "cached": False,
            "keyword": keyword,
            "analysis_type": analysis_type,
            "days": days,
            "boards": boards or [],
            "data": {
                "summary": "目前資料庫中找不到相關文章，請先執行爬蟲或更換關鍵字。",
                "hot_topics": [],
                "consumer_pain_points": [],
                "marketing_suggestions": [],
            },
        }

    # Note:
    # 壓縮文章，避免原文太長造成 token 太多。
    articles_context = compress_articles_for_llm(articles)

    # Note:
    # 根據 analysis_type 產生對應 prompt。
    prompt = build_prompt(
        analysis_type=analysis_type,
        keyword=keyword,
        articles_context=articles_context,
    )

    # Note:
    # 呼叫 Gemini API。若 Gemini 暫時過載，避免整個 API 回 500。
    try:
        raw_response = generate_json_response(prompt)
    except LLMServiceUnavailableError:
        return {
            "cached": False,
            "keyword": keyword,
            "analysis_type": analysis_type,
            "days": days,
            "boards": boards or [],
            "article_count": len(articles),
            "llm_unavailable": True,
            "data": {
                "summary": "AI 分析服務目前流量過高，暫時無法產生 LLM 洞察。Dashboard 的文章數、熱門文章、情緒與趨勢仍可正常查看，請稍後再按搜尋重試。",
                "hot_topics": [],
                "consumer_pain_points": [
                    "Gemini 模型目前回覆 503 high demand，這通常是暫時性狀況。",
                ],
                "marketing_suggestions": [
                    "先使用 Dashboard 的統計資料觀察趨勢，待模型恢復後再重新產生深度洞察。",
                ],
            },
        }

    # Note:
    # 把 Gemini 回傳的 JSON string 轉成 Python dict。
    result_json = parse_llm_json(raw_response)

    # Note:
    # 儲存到 analysis_results，作為下次使用的 cache。
    save_analysis_cache(
        db=db,
        keyword=keyword,
        analysis_type=cache_analysis_type,
        days=days,
        result_json=result_json,
    )

    return {
        "cached": False,
        "keyword": keyword,
        "analysis_type": analysis_type,
        "days": days,
        "boards": boards or [],
        "article_count": len(articles),
        "data": result_json,
    }
