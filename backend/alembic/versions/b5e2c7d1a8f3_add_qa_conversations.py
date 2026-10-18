"""store AI Q&A conversations per account

Revision ID: b5e2c7d1a8f3
Revises: a7d31c6f0e92
Create Date: 2026-10-18 23:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b5e2c7d1a8f3'
down_revision: Union[str, Sequence[str], None] = 'a7d31c6f0e92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """AI 問答對話改存資料庫，依帳號隔離（原本存在瀏覽器、所有帳號共用）。"""
    # 後端啟動時的 create_all 可能已先建好這張表，存在就略過。
    if "qa_conversations" in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        "qa_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("pinned", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "client_id", name="uq_qa_conversations_user_client"),
    )
    op.create_index("ix_qa_conversations_id", "qa_conversations", ["id"])
    op.create_index("ix_qa_conversations_user_id", "qa_conversations", ["user_id"])
    op.create_index("ix_qa_conversations_updated_at", "qa_conversations", ["updated_at"])


def downgrade() -> None:
    op.drop_table("qa_conversations")
