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
        description="要分析的關鍵字，例如：玻尿酸、肉毒、雷射",
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="查詢最近幾天的資料，例如：7、30、90",
    ),
    sort_by: str = Query(
        default="push_count",
        description="文章排序方式：push_count、latest、relevance",
    ),
    boards: list[str] | None = Query(
        default=None,
        description="要包含的 PTT 看板，重複此參數可選多個看板。",
    ),
    db: Session = Depends(get_db),
):
    """
    說明：
    Dashboard 的主要 API。

    前端 Dashboard 只需要呼叫這一支 API，
    就能拿到整個 dashboard 需要的全部資料。
    """

    # 用查詢參數組出 cache key，
    # 例如：dashboard:玻尿酸:30:push_count
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

    # 說明：
    # 寫入 cache，之後相同條件的查詢 10 分鐘內直接回 cache。
    # （修正：原本只有 get_cache 沒有 set_cache，cache 從未生效。）
    set_cache(cache_key, data, minutes=10)

    return {
        "status": "success",
        "cached": False,
        "data": data,
    }
