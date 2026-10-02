from collections import Counter

from app.core.time_utils import taiwan_now
from app.models.database_models import Article, ArticleChunk, Author, Board, Comment, Platform


def get_or_create_platform(db, name: str):
    platform = db.query(Platform).filter(Platform.name == name).first()

    if platform:
        return platform

    platform = Platform(
        name=name,
        display_name=name
    )

    db.add(platform)
    db.commit()
    db.refresh(platform)

    return platform


def get_or_create_board(db, platform_id: int, name: str):
    board = (
        db.query(Board)
        .filter(
            Board.platform_id == platform_id,
            Board.name == name
        )
        .first()
    )

    if board:
        return board

    board = Board(
        platform_id=platform_id,
        name=name,
        display_name=name
    )

    db.add(board)
    db.commit()
    db.refresh(board)

    return board


def get_or_create_author(db, username: str):
    if not username:
        username = "unknown"

    author = db.query(Author).filter(Author.username == username).first()

    if author:
        return author

    author = Author(
        username=username,
        display_name=username
    )

    db.add(author)
    db.commit()
    db.refresh(author)

    return author


def create_article(
    db,
    unique_id: str,
    platform_name: str,
    board_name: str,
    author_username: str,
    title: str,
    content: str,
    url: str,
    push_count: int = 0,
    published_at=None
):
    existing_article = (
        db.query(Article)
        .filter(Article.unique_id == unique_id)
        .first()
    )

    if existing_article:
        # Empty bodies can indicate a partial/failed fetch; preserve known text.
        next_title = title or existing_article.title
        next_content = content or existing_article.content
        if (next_title, next_content) != (existing_article.title, existing_article.content):
            old_body = (existing_article.content or "").split(COMMENT_SECTION_MARKER, 1)[0]
            new_body = (next_content or "").split(COMMENT_SECTION_MARKER, 1)[0]
            if next_title != existing_article.title or old_body != new_body:
                existing_article.sentiment = None
            # Search vectors must be regenerated for the new text/replies.
            db.query(ArticleChunk).filter(ArticleChunk.article_id == existing_article.id).delete(
                synchronize_session=False,
            )
        existing_article.title = next_title
        existing_article.content = next_content
        existing_article.push_count = push_count
        existing_article.url = url or existing_article.url
        if published_at is not None:
            existing_article.published_at = published_at
        existing_article.last_crawled_at = taiwan_now()
        db.commit()
        return existing_article, False

    platform = get_or_create_platform(db, platform_name)
    board = get_or_create_board(db, platform.id, board_name)
    author = get_or_create_author(db, author_username)

    # 說明：
    # 來源站台偶爾抓不到發文時間（置頂列、Threads 少數貼文沒有 <time>）。
    # published_at 若留成 NULL，這篇文章會被所有「日期區間」查詢排除，
    # 等於永遠不會出現在儀表板，也不會被排到情緒評分佇列。
    # 因此退而求其次，用「抓取當下的時間」當作發文時間。
    if published_at is None:
        published_at = taiwan_now()

    article = Article(
        unique_id=unique_id,
        platform_id=platform.id,
        board_id=board.id,
        author_id=author.id,
        title=title,
        content=content,
        url=url,
        push_count=push_count,
        published_at=published_at,
        last_crawled_at=taiwan_now(),
    )

    db.add(article)
    db.commit()
    db.refresh(article)

    return article, True

def save_comments(db, article, comments: list[str]) -> int:
    """
    說明：
    把爬到的留言存成 Comment（逐則一列），供「留言情緒」與
    「最負面留言」等細粒度分析使用。

    比對內容與出現次數，只新增尚未收錄的留言；部分抓取不刪除既有留言。
    回傳實際新增的筆數。
    """

    if not comments or article is None:
        return 0

    existing = db.query(Comment).filter(Comment.article_id == article.id).all()
    remaining = Counter(row.content.strip() for row in existing)
    floor = max((row.floor or 0 for row in existing), default=0)

    added = 0

    for text in comments:
        clean = (text or "").strip()

        if not clean:
            continue

        if remaining[clean]:
            remaining[clean] -= 1
            continue
        floor += 1
        db.add(Comment(article_id=article.id, floor=floor, content=clean))
        added += 1

    if added:
        db.commit()

    return added


# 爬蟲把留言併進內文時使用的分隔標記（見 BrowserCrawler._merge_content_and_replies）。
COMMENT_SECTION_MARKER = "【留言】"


def extract_comments_from_content(content: str | None) -> list[str]:
    """從文章內文的「【留言】」段落還原留言清單。

    爬蟲以「- 留言內容」的形式把每則留言寫進內文。留言本身可能換行，
    所以「不是以 - 開頭」的後續行要視為上一則留言的延續，不能當成新留言。
    """

    if not content or COMMENT_SECTION_MARKER not in content:
        return []

    section = content.split(COMMENT_SECTION_MARKER, 1)[1]
    comments: list[str] = []

    for line in section.splitlines():
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("- "):
            comments.append(stripped[2:].strip())
        elif comments:
            # 同一則留言的換行內容。
            comments[-1] = comments[-1] + chr(10) + stripped

    return [comment for comment in comments if comment]


def backfill_comments_from_content(db, limit: int | None = None) -> dict:
    """把既有文章內文裡的留言補寫進 comments 表。

    comments 表是後來才加入的，在那之前爬到的文章只把留言併在 content 裡。
    重新爬取救不回來（文章已存在會被視為重複而跳過），所以直接從內文還原。

    save_comments 會比對既有留言，因此本函式可重複執行不會重複新增。
    """

    query = (
        db.query(Article)
        .filter(Article.content.like(f"%{COMMENT_SECTION_MARKER}%"))
        .order_by(Article.id)
    )

    if limit:
        query = query.limit(limit)

    articles_done = 0
    comments_added = 0

    for article in query.all():
        added = save_comments(db, article, extract_comments_from_content(article.content))

        if added:
            articles_done += 1
            comments_added += added

    return {"articles": articles_done, "comments": comments_added}
