# backend/app/services/article_compressor.py

import re
from datetime import datetime, timedelta

from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.models.database_models import Article, Board


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_related_articles(
    db: Session,
    keyword: str,
    days: int = 30,
    limit: int = 30,
    boards: list[str] | None = None,
):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    keyword_like = f"%{keyword}%"

    query = (
        db.query(Article)
        .filter(
            or_(
                Article.title.ilike(keyword_like),
                Article.content.ilike(keyword_like),
            )
        )
        .filter(Article.published_at >= start_date)
        .filter(Article.published_at <= end_date)
    )

    if boards:
        query = query.filter(Article.board.has(Board.name.in_(boards)))

    return query.order_by(desc(Article.push_count)).limit(limit).all()


def compress_articles_for_llm(
    articles,
    max_chars_per_article: int = 400,
    max_total_chars: int = 15000,
) -> str:
    compressed_parts = []
    total_chars = 0

    for index, article in enumerate(articles, start=1):
        title = clean_text(article.title)
        content = clean_text(article.content)
        short_content = content[:max_chars_per_article]
        board_name = article.board.name if article.board else ""
        author_name = article.author.username if article.author else "unknown"

        article_text = f"""
Article {index}
Title: {title}
Board: {board_name}
Author: {author_name}
Push count: {article.push_count}
Published at: {article.published_at}
Content preview: {short_content}
URL: {article.url}
""".strip()

        if total_chars + len(article_text) > max_total_chars:
            break

        compressed_parts.append(article_text)
        total_chars += len(article_text)

    return "\n\n---\n\n".join(compressed_parts)
