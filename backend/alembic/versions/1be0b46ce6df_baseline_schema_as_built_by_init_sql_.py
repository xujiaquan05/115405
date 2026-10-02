"""baseline: schema as built by init.sql and startup migrations

Revision ID: 1be0b46ce6df
Revises: 
Create Date: 2026-09-08 16:48:58.425279

"""
from typing import Sequence, Union
from pathlib import Path

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1be0b46ce6df'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Bootstrap fresh databases before later revisions reference their tables.

    Previously this was empty and only worked for databases already initialized
    by startup. A frozen snapshot avoids coupling historical migrations to live
    ORM models. IF NOT EXISTS preserves pre-Alembic installations and their data.
    Databases already stamped at this revision do not rerun the baseline.
    """
    snapshot = Path(__file__).resolve().parents[1] / "baseline_schema.sql"
    for statement in snapshot.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.execute(sa.text(statement))


def downgrade() -> None:
    """基準版本沒有可回復的內容。"""
