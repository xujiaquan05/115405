"""baseline: schema as built by init.sql and startup migrations

Revision ID: 1be0b46ce6df
Revises: 
Create Date: 2026-09-08 16:48:58.425279

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1be0b46ce6df'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """基準版本，刻意留空。

    這個專案在導入 Alembic 之前，資料表是由 database/init.sql 建立，
    後續欄位則由 startup.py 的 ALTER TABLE ... IF NOT EXISTS 補上。
    現有資料庫已經是這個狀態，所以基準版本不做任何事，
    只用 `alembic stamp head` 標記「資料庫已在此版本」。

    從此之後的結構變更請一律建立新的 revision，
    才有版本歷史、才能 downgrade、也才能在 PR 中被審查。
    """


def downgrade() -> None:
    """基準版本沒有可回復的內容。"""
