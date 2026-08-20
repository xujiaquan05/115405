# backend/app/routers/articles.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database_models import Article, Comment


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
            "platform": article.platform.name if article.platform else None,
            "comments": _serialize_comments(article, db),
        },
    }


def _serialize_comments(article: Article, db: Session) -> dict:
    """
    說明：
    回傳這篇文章的留言與情緒統計。

    留言雖然也併在 content 裡供整體分析，但獨立出來後才能回答
    「有幾則留言」「負面比例多少」「最負面的留言是哪幾則」。
    """

    comments = (
        db.query(Comment)
        .filter(Comment.article_id == article.id)
        .order_by(Comment.floor)
        .all()
    )

    if not comments:
        return {"total": 0, "rated": 0, "positive": 0, "neutral": 0, "negative": 0, "items": []}

    counts = {"positive": 0, "neutral": 0, "negative": 0}

    for comment in comments:
        if comment.sentiment in counts:
            counts[comment.sentiment] += 1

    rated = sum(counts.values())

    return {
        "total": len(comments),
        "rated": rated,
        # 比例以「已評分留言」為分母，未評分不列入。
        "positive": round(counts["positive"] / rated * 100, 1) if rated else 0,
        "neutral": round(counts["neutral"] / rated * 100, 1) if rated else 0,
        "negative": round(counts["negative"] / rated * 100, 1) if rated else 0,
        "items": [
            {
                "floor": comment.floor,
                "content": comment.content,
                "sentiment": comment.sentiment,
            }
            for comment in comments
        ],
    }
