"""add article_embeddings for semantic retrieval

Revision ID: b7c2e1f40a93
Revises: 65ddfa4c7c98
Create Date: 2026-09-21 00:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7c2e1f40a93'
down_revision: Union[str, Sequence[str], None] = '65ddfa4c7c98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """建立存放文章語意向量的資料表。

    同樣捨棄 autogenerate 的產出：它夾帶了一批與本次無關的既有差異
    （索引命名、JSONB 對 JSON、甚至要刪掉 analysis_results.user_id），
    套下去會動到不該動的東西。這裡只做真正要做的事。

    向量存成 bytea（float32 小端序），不是 pgvector 的 vector 型別：
    這台資料庫沒有 vector 擴充，而目前規模用 Python 精確計算餘弦相似度
    只要幾毫秒。日後要換 pgvector，改的就是這個欄位與查詢函式。
    """
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    # 開發機以 --reload 執行時，startup 的 create_all 會搶先建好這張表，
    # Alembic 反而看不到「新增」。有這道檢查兩種情況都能安全執行。
    if "article_embeddings" in existing:
        return

    op.create_table(
        "article_embeddings",
        sa.Column("article_id", sa.Integer(), primary_key=True),
        sa.Column("model", sa.String(length=50), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("article_embeddings")
