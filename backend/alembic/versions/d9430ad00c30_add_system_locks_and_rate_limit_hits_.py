"""add system_locks and rate_limit_hits for shared state

Revision ID: d9430ad00c30
Revises: 1be0b46ce6df
Create Date: 2026-09-08 21:47:35.028362

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd9430ad00c30'
down_revision: Union[str, Sequence[str], None] = '1be0b46ce6df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """建立跨行程共享狀態用的兩張表。

    autogenerate 產出的內容已捨棄不用：它同時夾帶了一批既有的索引 / 約束
    命名差異（init.sql 與 SQLAlchemy 慣例不同），套用下去會動到與本次無關的東西。
    這裡只留真正要做的事。

    另外用 inspector 檢查是否已存在：開發機的 app 以 --reload 執行時，
    startup 的 create_all 會搶先把新表建好，Alembic 反而看不到「新增」。
    這個防護讓 migration 在兩種情況下都能安全執行。
    """
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "system_locks" not in existing:
        op.create_table(
            "system_locks",
            sa.Column("name", sa.String(length=64), primary_key=True),
            sa.Column("acquired_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("owner", sa.String(length=64), nullable=True),
        )

    if "rate_limit_hits" not in existing:
        op.create_table(
            "rate_limit_hits",
            sa.Column("key", sa.String(length=200), primary_key=True),
            sa.Column("window_start", sa.DateTime(), nullable=False),
            sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_table("rate_limit_hits")
    op.drop_table("system_locks")
