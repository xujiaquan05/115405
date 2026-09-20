"""語意向量（embedding）：讓 RAG 能檢索「意思相近」而不只是「字面相同」。

原本的檢索是 SQL 的 ILIKE：使用者問「打完玻尿酸臉會不會腫」，
只有內文真的出現「玻尿酸」三個字的文章才找得到；
寫成「填充物」「填劑」「微整針劑」的文章一篇都撈不到。

向量檢索把問題與文章都轉成同一個語意空間裡的座標，
用餘弦相似度找出最接近的文章，用詞不同也找得到。

兩種檢索各有盲點，因此 rag_service 是兩邊都跑再合併：
- 關鍵字強在專有名詞（診所名、品牌名），但換句話說就失效。
- 向量強在換句話說，但可能漏掉「只差一個字」的精確匹配。
"""

import logging
import struct

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database_models import Article, ArticleEmbedding
from app.services.article_compressor import clean_text, split_main_and_comments
from app.services.llm_client import LLMServiceUnavailableError, get_gemini_client

logger = logging.getLogger(__name__)

# Gemini 的向量模型。與對話模型分開設定：
# 換對話模型不需要重算向量，換向量模型才需要。
EMBEDDING_MODEL = "gemini-embedding-001"

# 768 維：這個模型支援 128～3072，維度越高越準也越佔空間。
# 以本專案規模（近一萬篇）768 維已足夠，一篇佔 3KB，全部約 30MB。
EMBEDDING_DIMENSIONS = 768

# 一次送幾篇給 API。
EMBED_BATCH_SIZE = 50

# 每回合最多處理幾篇，避免一次佔用太多額度。
MAX_ARTICLES_PER_RUN = 500

# 送去產生向量的文字長度上限。
# 標題加主文開頭通常就決定了一篇文章在講什麼；
# 整篇丟進去反而會把主題稀釋掉（長討論串尤其明顯）。
MAX_EMBED_CHARS = 1000


def pack_vector(values: list[float]) -> bytes:
    """把向量打包成 float32 位元組，方便存進 bytea。"""
    return struct.pack(f"<{len(values)}f", *values)


def unpack_vector(raw: bytes) -> list[float]:
    """把 bytea 還原成 float 清單（測試與除錯用）。"""
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))


def text_for_embedding(article: Article) -> str:
    """組出要送去產生向量的文字。

    只取主文：留言是別人的意見，混進來會讓向量代表「整串討論的平均」，
    反而不容易對上使用者問的那件事。留言仍由關鍵字檢索負責。
    """
    main_text, _comments = split_main_and_comments(clean_text(article.content or ""))
    title = clean_text(article.title or "")

    return f"{title}\n{main_text}"[:MAX_EMBED_CHARS].strip()


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


def embed_pending_articles(
    db: Session,
    max_articles: int = MAX_ARTICLES_PER_RUN,
    batch_size: int = EMBED_BATCH_SIZE,
) -> int:
    """為還沒有向量的文章產生向量，新文章優先。回傳成功產生的篇數。

    和情緒評分一樣：Gemini 忙碌就提早結束，剩下的留給下一回合，
    不把例外往外拋，免得整個爬取流程因此中斷。
    """
    pending = (
        db.query(Article)
        .outerjoin(ArticleEmbedding, ArticleEmbedding.article_id == Article.id)
        .filter(ArticleEmbedding.article_id.is_(None))
        .order_by(Article.published_at.desc().nullslast())
        .limit(max_articles)
        .all()
    )

    if not pending:
        return 0

    created = 0

    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        texts = [text_for_embedding(article) for article in batch]

        # 內容全空的文章沒有東西可以向量化，跳過即可。
        usable = [(article, text) for article, text in zip(batch, texts, strict=True) if text]

        if not usable:
            continue

        try:
            vectors = embed_texts([text for _article, text in usable])
        except LLMServiceUnavailableError:
            logger.warning("Gemini embedding unavailable, stopped after %s articles", created)
            break
        except Exception:
            logger.exception("Embedding failed, stopping this run")
            break

        for (article, _text), values in zip(usable, vectors, strict=True):
            db.add(ArticleEmbedding(
                article_id=article.id,
                model=EMBEDDING_MODEL,
                dimensions=len(values),
                vector=pack_vector(values),
            ))
            created += 1

        db.commit()

    return created


def count_pending_embeddings(db: Session) -> int:
    """還有幾篇文章沒有向量。"""
    return (
        db.query(Article)
        .outerjoin(ArticleEmbedding, ArticleEmbedding.article_id == Article.id)
        .filter(ArticleEmbedding.article_id.is_(None))
        .count()
    )


def rank_by_similarity(
    db: Session,
    query_text: str,
    candidate_ids: list[int],
    limit: int = 12,
) -> list[tuple[int, float]]:
    """在指定的候選文章中，找出語意上最接近問題的幾篇。

    回傳 [(article_id, 相似度)]，相似度由高到低。

    為什麼先由 SQL 篩出候選，而不是對全庫做相似度？
    時間範圍與平台是使用者給的硬條件，不該被語意相似度覆蓋——
    問「最近一週」就不該回一年前的文章，即使那篇語意更接近。
    篩完之後候選通常只有幾百篇，精確計算餘弦相似度只要幾毫秒，
    不需要近似最近鄰索引。
    """
    import numpy as np

    if not candidate_ids or not query_text:
        return []

    rows = db.execute(
        select(ArticleEmbedding.article_id, ArticleEmbedding.vector)
        .where(ArticleEmbedding.article_id.in_(candidate_ids))
    ).all()

    if not rows:
        return []

    try:
        query_vector = embed_texts([query_text], task_type="RETRIEVAL_QUERY")[0]
    except Exception:
        # 向量檢索失敗不該讓整個問答掛掉，交給關鍵字檢索就好。
        logger.warning("Could not embed the question, falling back to keyword search only")
        return []

    article_ids = [row[0] for row in rows]
    matrix = np.frombuffer(b"".join(row[1] for row in rows), dtype=np.float32)
    matrix = matrix.reshape(len(article_ids), -1)

    query_array = np.asarray(query_vector, dtype=np.float32)

    # 餘弦相似度：正規化後做內積。加 1e-12 避免零向量除以零。
    matrix_norms = np.linalg.norm(matrix, axis=1) + 1e-12
    scores = (matrix @ query_array) / (matrix_norms * (np.linalg.norm(query_array) + 1e-12))

    ranked = sorted(zip(article_ids, scores.tolist(), strict=True), key=lambda pair: -pair[1])

    return ranked[:limit]
