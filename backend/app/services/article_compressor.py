# backend/app/services/article_compressor.py

import re
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.models.database_models import Article


def clean_text(text: str) -> str:
    """
    Note:
    Dọn nội dung bài viết trước khi gửi cho LLM.

    Vì nội dung PTT thường có:
    - nhiều dòng trống
    - khoảng trắng dư
    - ký tự xuống dòng liên tục

    Nếu không dọn, token sẽ bị lãng phí.
    """

    if not text:
        return ""

    # Note:
    # Chuyển nhiều khoảng trắng / xuống dòng thành 1 khoảng trắng.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_related_articles(
    db: Session,
    keyword: str,
    days: int = 30,
    limit: int = 30,
):
    """
    Note:
    Lấy các bài viết liên quan đến keyword trong database.

    Điều kiện:
    - title chứa keyword hoặc content chứa keyword
    - nằm trong số ngày user chọn
    - ưu tiên bài có push_count cao

    limit=30 để tránh gửi quá nhiều bài cho LLM.
    """

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    keyword_like = f"%{keyword}%"

    articles = (
        db.query(Article)
        .filter(
            or_(
                Article.title.ilike(keyword_like),
                Article.content.ilike(keyword_like),
            )
        )
        .filter(Article.published_at >= start_date)
        .filter(Article.published_at <= end_date)
        .order_by(desc(Article.push_count))
        .limit(limit)
        .all()
    )

    return articles


def compress_articles_for_llm(
    articles,
    max_chars_per_article: int = 400,
    max_total_chars: int = 15000,
) -> str:
    """
    Note:
    Nén danh sách bài viết thành một đoạn text ngắn để gửi cho LLM.

    Quy tắc:
    - Mỗi bài chỉ lấy tối đa 400 chữ đầu.
    - Tổng toàn bộ context không vượt quá 15000 chữ.
    - Nếu vượt quá thì dừng lại, không thêm bài nữa.

    Vì sao phải làm vậy?
    - Giảm token
    - Giảm chi phí
    - Giảm nguy cơ Gemini trả lời chậm
    """

    compressed_parts = []
    total_chars = 0

    for index, article in enumerate(articles, start=1):
        title = clean_text(article.title)
        content = clean_text(article.content)

        short_content = content[:max_chars_per_article]

        article_text = f"""
文章 {index}
標題: {title}
看板: {article.board}
作者: {article.author}
推文數: {article.push_count}
日期: {article.published_at}
內容摘要: {short_content}
原文連結: {article.url}
""".strip()

        # Note:
        # 如果加 bài này vào sẽ vượt quá tổng giới hạn,
        # thì dừng lại để bảo vệ token limit.
        if total_chars + len(article_text) > max_total_chars:
            break

        compressed_parts.append(article_text)
        total_chars += len(article_text)

    return "\n\n---\n\n".join(compressed_parts)