"""replace whole-article embeddings with per-chunk embeddings

Revision ID: c3e8a91d7b45
Revises: b7c2e1f40a93
Create Date: 2026-09-21 01:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3e8a91d7b45'
down_revision: Union[str, Sequence[str], None] = 'b7c2e1f40a93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """改成「一篇文章多段向量」。

    原本一篇文章只有一個向量，而且為了控制長度只取前 1000 字。
    實測資料庫裡有 1,138 篇超過這個長度，合計 772,722 字
    （全部內容的 16%）從來沒有進過向量，等於搜不到。
    一個向量也只能代表一個主題，長文的各段特徵會被平均掉。

    舊的向量無法沿用：切段後每一段的文字都與原本的「標題＋前 1000 字」
    不同，向量自然也不同，只能重新產生（backfill_embeddings.py）。
    因此這裡直接刪掉舊表，不留下一張沒人讀的資料。
    """
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    # 開發機以 --reload 執行時，startup 的 create_all 會搶先建好新表。
    if "article_chunks" not in existing:
        op.create_table(
            "article_chunks",
            sa.Column("article_id", sa.Integer(), primary_key=True),
            sa.Column("chunk_index", sa.Integer(), primary_key=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("model", sa.String(length=50), nullable=False),
            sa.Column("dimensions", sa.Integer(), nullable=False),
            sa.Column("vector", sa.LargeBinary(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        )

    if "article_embeddings" in existing:
        op.drop_table("article_embeddings")


def downgrade() -> None:
    op.create_table(
        "article_embeddings",
        sa.Column("article_id", sa.Integer(), primary_key=True),
        sa.Column("model", sa.String(length=50), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
    )
    op.drop_table("article_chunks")
