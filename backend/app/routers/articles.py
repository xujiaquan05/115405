# backend/app/routers/articles.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database_models import Article


router = APIRouter(
    prefix="/api/articles",
    tags=["Articles"],
)


@router.get("/{article_id}")
def get_article(article_id: int, db: Session = Depends(get_db)):
    """
    說明：
    取得單篇文章的完整資料（內容、情緒、來源），供文章詳情頁使用。
    唯讀，不需登入。
    """

    article = db.query(Article).filter(Article.id == article_id).first()

    if article is None:
        raise HTTPException(status_code=404, detail="找不到此文章。")

    return {
        "status": "success",
        "data": {
            "id": article.id,
            "title": article.title,
            "content": article.content or "",
            "board": article.board.name if article.board else "",
            "author": article.author.username if article.author else "unknown",
            "push_count": article.push_count or 0,
            "sentiment": article.sentiment,
            "url": article.url,
            "published_at": article.published_at.strftime("%Y-%m-%d %H:%M:%S")
            if article.published_at else None,
        },
    }
