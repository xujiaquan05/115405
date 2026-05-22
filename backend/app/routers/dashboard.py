# backend/app/routers/dashboard.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.dashboard_service import get_dashboard_full, normalize_boards

from app.services.cache_service import get_cache, set_cache


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get("/full")
def dashboard_full(
    keyword: str = Query(
        default="玻尿酸",
        description="Keyword muốn phân tích, ví dụ: 玻尿酸, 肉毒, 雷射",
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Số ngày muốn truy vấn, ví dụ: 7, 30, 90",
    ),
    sort_by: str = Query(
        default="push_count",
        description="Cách sắp xếp bài viết: push_count, latest, relevance",
    ),
    boards: list[str] | None = Query(
        default=None,
        description="PTT boards to include. Repeat this query parameter to select multiple boards.",
    ),
    db: Session = Depends(get_db),
):
    """
    Note:
    API chính của Phase 3.

    Frontend Dashboard sau này chỉ cần gọi API này một lần
    là lấy được đủ dữ liệu cho toàn bộ dashboard.
    """

    # Note:
    # Tạo cache key từ tham số query.
    # Ví dụ: dashboard:玻尿酸:30:push_count
    selected_boards = normalize_boards(boards)
    boards_key = ",".join(selected_boards)
    cache_key = f"dashboard:{keyword}:{days}:{sort_by}:{boards_key}"

    cached_data = get_cache(cache_key)

    if cached_data is not None:
        return {
            "status": "success",
            "cached": True,
            "cache_key": cache_key,
            "data": cached_data,
        }

    data = get_dashboard_full(
        db=db,
        keyword=keyword,
        days=days,
        sort_by=sort_by,
        boards=selected_boards,
    )

    return {
        "status": "success",
        "cached": False,
        "data": data,
    }
