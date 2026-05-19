# backend/app/routers/analysis.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.llm_analysis_service import analyze_keyword_with_llm


router = APIRouter(
    prefix="/api/analysis",
    tags=["LLM Analysis"],
)


@router.get("/keyword")
def analyze_keyword(
    keyword: str = Query(
        default="玻尿酸",
        description="Keyword muốn phân tích, ví dụ: 玻尿酸, 肉毒, 雷射",
    ),
    analysis_type: str = Query(
        default="overview",
        description="Loại phân tích: overview, trend, sentiment",
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Phân tích bài viết trong bao nhiêu ngày gần đây",
    ),
    force_refresh: bool = Query(
        default=False,
        description="True = bỏ qua cache và gọi Gemini lại",
    ),
    db: Session = Depends(get_db),
):
    """
    Note:
    API chính của Phase 4.

    Ví dụ:
    /api/analysis/keyword?keyword=玻尿酸&analysis_type=overview&days=30

    analysis_type:
    - overview: phân tích tổng hợp
    - trend: phân tích xu hướng
    - sentiment: phân tích cảm xúc
    """

    result = analyze_keyword_with_llm(
        db=db,
        keyword=keyword,
        analysis_type=analysis_type,
        days=days,
        force_refresh=force_refresh,
    )

    return {
        "status": "success",
        "result": result,
    }