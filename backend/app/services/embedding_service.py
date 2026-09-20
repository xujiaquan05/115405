"""語意向量（embedding）：讓 RAG 能檢索「意思相近」而不只是「字面相同」。

原本的檢索是 SQL 的 ILIKE：使用者問「打完填充物臉會不會腫」，
只有內文真的出現「填充物」三個字的文章才找得到；
寫成「玻尿酸」「微整針劑」的文章一篇都撈不到。

向量檢索把問題與文章都轉成同一個語意空間裡的座標，
用餘弦相似度找出最接近的文章，用詞不同也找得到。

兩種檢索各有盲點，因此 rag_service 是兩邊都跑再合併：
- 關鍵字強在專有名詞（診所名、品牌名），但換句話說就失效。
- 向量強在換句話說，但可能漏掉「只差一個字」的精確匹配。

文章是切成小段各自產生向量，理由見 ArticleChunk 的說明。
"""

import logging
import struct

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database_models import Article, ArticleChunk
from app.services.article_compressor import clean_text
from app.services.llm_client import LLMServiceUnavailableError, get_gemini_client

logger = logging.getLogger(__name__)

# Gemini 的向量模型。與對話模型分開設定：
# 換對話模型不需要重算向量，換向量模型才需要。
EMBEDDING_MODEL = "gemini-embedding-001"

# 768 維：這個模型支援 128～3072，維度越高越準也越佔空間。
# 以本專案規模 768 維已足夠，一段佔 3KB。
EMBEDDING_DIMENSIONS = 768

# 一次送幾段給 API。
EMBED_BATCH_SIZE = 50

# 每回合最多處理幾篇文章，避免一次佔用太多額度。
MAX_ARTICLES_PER_RUN = 300

# 每段的長度與相鄰兩段的重疊字數。
# 重疊是為了避免剛好被切斷的句子兩邊都拼不完整——
# 「術後前三天會腫 / 之後就慢慢消了」被切在中間的話，
# 問「消腫要多久」兩段都只對上一半。
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80

# 單篇最多切幾段，避免極長的文章一口氣吃掉整批額度。
# 實測最長的文章 10,064 字，約 30 段。
MAX_CHUNKS_PER_ARTICLE = 30


def pack_vector(values: list[float]) -> bytes:
    """把向量打包成 float32 位元組，方便存進 bytea。"""
    return struct.pack(f"<{len(values)}f", *values)


def unpack_vector(raw: bytes) -> list[float]:
    """把 bytea 還原成 float 清單（測試與除錯用）。"""
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))


def split_into_chunks(article: Article) -> list[str]:
    """把一篇文章切成數段，每段都是要拿去產生向量的文字。

    每一段前面都補上標題：從文章中段切出來的片段常常只有代名詞
    （「它效果不錯」的「它」是什麼？），補上標題才知道在講哪個療程。
    代價是同一篇的各段會變得比較像，這是刻意的取捨——
    段落太短而沒有主題，比段落之間不夠分散更糟。

    留言（【留言】段落）不特別處理，跟著一起切：
    每則留言自成一段獨立的意見，正是單一向量做不到的事。
    """
    title = clean_text(article.title or "")
    body = clean_text(article.content or "")

    if not body:
        return [title] if title else []

    chunks: list[str] = []
    step = CHUNK_SIZE - CHUNK_OVERLAP

    for start in range(0, len(body), step):
        piece = body[start:start + CHUNK_SIZE]

        if piece.strip():
            chunks.append(f"{title}\n{piece}".strip() if title else piece)

        if len(chunks) >= MAX_CHUNKS_PER_ARTICLE or start + CHUNK_SIZE >= len(body):
            break

    return chunks


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """把多段文字一次送去產生向量。

    task_type 要分清楚：文章用 RETRIEVAL_DOCUMENT、查詢用 RETRIEVAL_QUERY。
    這個模型會依用途調整向量，用錯會讓相似度下降。
    """
    from google.genai import errors, types

    if not texts:
        return []

    client = get_gemini_client()

    try:
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSIONS,
                task_type=task_type,
            ),
        )
    except errors.APIError as error:
        # 與 llm_client 一致：429 與 5xx 視為暫時性，讓呼叫端決定要不要重試。
        if error.code == 429 or (error.code is not None and error.code >= 500):
            raise LLMServiceUnavailableError("Gemini embedding is busy or out of quota.") from error

        raise

    return [list(item.values) for item in response.embeddings]


def _pending_articles(db: Session, max_articles: int) -> list[Article]:
    """還沒有任何段落向量的文章，新文章優先。"""
    return (
        db.query(Article)
        .outerjoin(ArticleChunk, ArticleChunk.article_id == Article.id)
        .filter(ArticleChunk.article_id.is_(None))
        .order_by(Article.published_at.desc().nullslast())
        .limit(max_articles)
        .all()
    )


def _store_article_chunks(db: Session, pending: list[tuple[Article, list[str]]]) -> int:
    """送出一批段落並寫入資料庫，回傳成功寫入的段落數。"""
    texts = [text for _article, chunks in pending for text in chunks]

    if not texts:
        return 0

    vectors = embed_texts(texts)
    position = 0

    for article, chunks in pending:
        for chunk_index, text in enumerate(chunks):
            db.add(ArticleChunk(
                article_id=article.id,
                chunk_index=chunk_index,
                content=text,
                model=EMBEDDING_MODEL,
                dimensions=len(vectors[position]),
                vector=pack_vector(vectors[position]),
            ))
            position += 1

    db.commit()

    return position


def embed_pending_articles(
    db: Session,
    max_articles: int = MAX_ARTICLES_PER_RUN,
    batch_size: int = EMBED_BATCH_SIZE,
) -> int:
    """為還沒有向量的文章切段並產生向量。回傳成功產生的段落數。

    和情緒評分一樣：Gemini 忙碌就提早結束，剩下的留給下一回合，
    不把例外往外拋，免得整個爬取流程因此中斷。
    """
    articles = _pending_articles(db, max_articles)

    if not articles:
        return 0

    created = 0
    batch: list[tuple[Article, list[str]]] = []
    batch_size_so_far = 0

    def flush() -> int:
        try:
            return _store_article_chunks(db, batch)
        except LLMServiceUnavailableError:
            raise
        except Exception:
            logger.exception("Embedding failed for a batch of %d articles", len(batch))
            db.rollback()
            return 0

    for article in articles:
        chunks = split_into_chunks(article)

        if not chunks:
            continue

        # 一篇文章的所有段落必須留在同一批：
        # 拆到兩批的話，中間失敗就會留下「有一部分段落」的文章，
        # 而待處理清單是用「完全沒有段落」判斷的，這篇就再也補不齊了。
        if batch and batch_size_so_far + len(chunks) > batch_size:
            try:
                created += flush()
            except LLMServiceUnavailableError:
                logger.warning("Gemini embedding unavailable, stopped after %s chunks", created)
                return created

            batch = []
            batch_size_so_far = 0

        batch.append((article, chunks))
        batch_size_so_far += len(chunks)

    if batch:
        try:
            created += flush()
        except LLMServiceUnavailableError:
            logger.warning("Gemini embedding unavailable, stopped after %s chunks", created)

    return created


def count_pending_embeddings(db: Session) -> int:
    """還有幾篇文章沒有任何段落向量。"""
    return (
        db.query(Article)
        .outerjoin(ArticleChunk, ArticleChunk.article_id == Article.id)
        .filter(ArticleChunk.article_id.is_(None))
        .count()
    )


def rank_by_similarity(
    db: Session,
    query_text: str,
    candidate_ids,
    limit: int = 12,
) -> list[tuple[int, float, str]]:
    """在指定的候選文章中，找出語意上最接近問題的幾篇。

    回傳 [(article_id, 相似度, 命中的那一段原文)]，相似度由高到低。

    一篇文章有多段向量，取「最像的那一段」當作這篇的分數，不取平均：
    一篇長文只要有一段正好回答了問題，這篇就該被找出來，
    取平均會被其他不相關的段落拉低而埋掉。

    為什麼先由 SQL 篩出候選，而不是對全庫做相似度？
    時間範圍與平台是使用者給的硬條件，不該被語意相似度覆蓋——
    問「最近一週」就不該回一年前的文章，即使那篇語意更接近。
    """
    import numpy as np

    if not query_text:
        return []

    if isinstance(candidate_ids, (list, tuple, set)) and not candidate_ids:
        return []

    rows = db.execute(
        select(ArticleChunk.article_id, ArticleChunk.content, ArticleChunk.vector)
        .where(ArticleChunk.article_id.in_(candidate_ids))
    ).all()

    if not rows:
        return []

    try:
        query_vector = embed_texts([query_text], task_type="RETRIEVAL_QUERY")[0]
    except Exception:
        # 向量檢索失敗不該讓整個問答掛掉，交給關鍵字檢索就好。
        logger.warning("Could not embed the question, falling back to keyword search only")
        return []

    matrix = np.frombuffer(b"".join(row[2] for row in rows), dtype=np.float32)
    matrix = matrix.reshape(len(rows), -1)

    query_array = np.asarray(query_vector, dtype=np.float32)

    # 餘弦相似度：正規化後做內積。加 1e-12 避免零向量除以零。
    matrix_norms = np.linalg.norm(matrix, axis=1) + 1e-12
    scores = (matrix @ query_array) / (matrix_norms * (np.linalg.norm(query_array) + 1e-12))

    # 同一篇文章只留分數最高的那一段。
    best: dict[int, tuple[float, str]] = {}

    for row, score in zip(rows, scores.tolist(), strict=True):
        article_id, content = row[0], row[1]

        if article_id not in best or score > best[article_id][0]:
            best[article_id] = (score, content)

    ranked = sorted(
        ((article_id, score, content) for article_id, (score, content) in best.items()),
        key=lambda item: -item[1],
    )

    return ranked[:limit]
