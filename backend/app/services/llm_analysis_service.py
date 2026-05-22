# backend/app/services/llm_analysis_service.py

import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.database_models import AnalysisResult
from app.services.article_compressor import (
    get_related_articles,
    compress_articles_for_llm,
)
from app.services.llm_prompts import build_prompt
from app.services.llm_client import generate_json_response


CACHE_HOURS = 6


def get_cached_analysis(
    db: Session,
    keyword: str,
    analysis_type: str,
    days: int,
):
    """
    Note:
    Kiểm tra xem keyword + analysis_type + days đã có cache chưa.

    Nếu có cache và chưa hết hạn:
    - trả kết quả cũ
    - không gọi Gemini API

    Nếu không có hoặc đã hết hạn:
    - return None
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
    Note:
    Lưu kết quả phân tích vào database.

    expires_at = hiện tại + 6 giờ.
    Trong 6 giờ đó nếu user hỏi lại cùng điều kiện,
    backend sẽ lấy cache thay vì gọi Gemini.
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

    db.commit()

def parse_llm_json(raw_text: str) -> dict:
    """
    Note:
    Chuyển text Gemini trả về thành dict Python.

    Dù đã yêu cầu JSON mode, mình vẫn thêm try/except
    để tránh trường hợp LLM trả về format không hợp lệ làm server crash.
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
    Note:
    Đây là hàm chính của Phase 4.

    Quy trình:
    1. Kiểm tra cache trong analysis_results
    2. Nếu có cache thì trả cache
    3. Nếu không có cache thì query articles
    4. Nén bài viết
    5. Tạo prompt
    6. Gọi Gemini
    7. Parse JSON
    8. Lưu kết quả vào cache
    9. Trả kết quả cho API
    """

    # Note:
    # Nếu force_refresh=False thì ưu tiên dùng cache.
    # Nếu force_refresh=True thì bỏ qua cache và gọi Gemini lại.
    boards_key = ",".join(boards or [])
    cache_analysis_type = f"{analysis_type}:{boards_key}" if boards_key else analysis_type

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

    # Note:
    # Lấy bài viết liên quan từ bảng articles.
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
    # 呼叫 Gemini API。
    raw_response = generate_json_response(prompt)

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
