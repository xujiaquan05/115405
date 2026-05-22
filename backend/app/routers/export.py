# backend/app/routers/export.py

from io import BytesIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.dashboard_service import normalize_boards
from app.services.export_service import build_articles_xlsx, get_export_articles


router = APIRouter(
    prefix="/api/export",
    tags=["Export"],
)


@router.get("/articles.xlsx")
def export_articles(
    keyword: str = Query(default="玻尿酸"),
    days: int = Query(default=30, ge=1, le=365),
    sort_by: str = Query(default="push_count"),
    boards: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    selected_boards = normalize_boards(boards)
    articles = get_export_articles(
        db=db,
        keyword=keyword,
        days=days,
        sort_by=sort_by,
        boards=selected_boards,
    )

    xlsx_bytes = build_articles_xlsx(articles)
    filename = f"articles_{days}d.xlsx"

    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
