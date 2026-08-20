from app.core.time_utils import taiwan_now
from app.models.database_models import Platform, Board, Author, Article, Comment


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
        published_at=published_at
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

    只在文章還沒有留言時寫入，避免重複爬取時同一篇文章的留言被灌爆。
    回傳實際新增的筆數。
    """

    if not comments or article is None:
        return 0

    if db.query(Comment).filter(Comment.article_id == article.id).first() is not None:
        return 0

    added = 0

    for index, text in enumerate(comments, start=1):
        clean = (text or "").strip()

        if not clean:
            continue

        db.add(Comment(article_id=article.id, floor=index, content=clean))
        added += 1

    if added:
        db.commit()

    return added
