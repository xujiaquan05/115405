"""split analysis history from the shared LLM cache

Revision ID: 65ddfa4c7c98
Revises: d9430ad00c30
Create Date: 2026-09-13 22:08:22.796822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65ddfa4c7c98'
down_revision: Union[str, Sequence[str], None] = 'd9430ad00c30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """把「使用者的分析歷史」從共用的 LLM 快取中拆出來。

    analysis_results 是以 keyword 為鍵的共用快取，同一個關鍵字只有一筆，
    讓多位客戶分析同一個關鍵字時只需呼叫一次 Gemini。
    先前歷史頁直接讀這張表，造成兩個問題：
    - 客戶看得到別人分析過哪些關鍵字
    - 刪除「自己的紀錄」實際刪掉共用快取，害所有人重付一次 Gemini 費用

    因此新增 analysis_history 存每位使用者的紀錄，
    並移除先前加在 analysis_results 上、實際從未被使用的 user_id 欄位。
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "analysis_history" not in inspector.get_table_names():
        op.create_table(
            "analysis_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("keyword", sa.String(length=255), nullable=False),
            sa.Column("analysis_type", sa.String(length=50), nullable=False),
            sa.Column("days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("result_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_analysis_history_user_id", "analysis_history", ["user_id"])

    columns = {c["name"] for c in inspector.get_columns("analysis_results")}

    if "user_id" in columns:
        op.drop_column("analysis_results", "user_id")


def downgrade() -> None:
    op.add_column("analysis_results", sa.Column("user_id", sa.Integer(), nullable=True))
    op.drop_index("ix_analysis_history_user_id", table_name="analysis_history")
    op.drop_table("analysis_history")
