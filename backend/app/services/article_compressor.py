# backend/app/services/article_compressor.py

import re
from datetime import timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.time_utils import taiwan_now
from app.models.database_models import Article, Board
from app.services.article_service import COMMENT_SECTION_MARKER
from app.services.dashboard_service import build_keyword_filter


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
    end_date = taiwan_now()
    start_date = end_date - timedelta(days=days)

    query = (
        db.query(Article)
        .filter(build_keyword_filter(keyword))
        .filter(Article.published_at >= start_date)
        .filter(Article.published_at <= end_date)
    )

    if boards:
        query = query.filter(Article.board.has(Board.name.in_(boards)))

    return query.order_by(desc(Article.push_count)).limit(limit).all()


def split_main_and_comments(content: str) -> tuple[str, str]:
    """把內文拆成 (主文, 留言)。

    Dcard / Mobile01 / Threads 的爬蟲會把留言接在主文後面的「【留言】」段落，
    PTT 目前沒有留言內容，回傳的留言就是空字串。
    """
    if COMMENT_SECTION_MARKER not in content:
        return content, ""

    main_text, comment_text = content.split(COMMENT_SECTION_MARKER, 1)

    return main_text.strip(), comment_text.strip()


def compress_articles_for_llm(
    articles,
    max_chars_per_article: int = 400,
    max_total_chars: int = 15000,
    max_comment_chars: int = 300,
) -> str:
    """把文章壓縮成一段送給 LLM 的文字。

    留言另外給一段額度，不跟主文搶。
    原本只取內文前 N 字，而留言接在主文後面，等於永遠被截掉——
    但檢索是用 ILIKE 搜整個 content，留言也算數。
    結果是「因為某則留言提到關鍵字而被選中的文章」，
    那則留言卻進不了 prompt，模型看不到它被選中的理由。
    """
    compressed_parts = []
    total_chars = 0

    for index, article in enumerate(articles, start=1):
        title = clean_text(article.title)
        main_text, comment_text = split_main_and_comments(clean_text(article.content))
        short_content = main_text[:max_chars_per_article]
        short_comments = comment_text[:max_comment_chars]
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

        # 有留言才加這一段，避免在沒有留言的 PTT 文章後面留下空標題。
        if short_comments:
            article_text += f"\nComments: {short_comments}"

        if total_chars + len(article_text) > max_total_chars:
            break

        compressed_parts.append(article_text)
        total_chars += len(article_text)

    return "\n\n---\n\n".join(compressed_parts)
