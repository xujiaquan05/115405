"""Record the most recent successful fetch of an article.

Revision ID: f1a92b3c4d56
Revises: e4f70c2a9d18
"""

import sqlalchemy as sa
from alembic import op

revision = "f1a92b3c4d56"
down_revision = "e4f70c2a9d18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {col["name"] for col in sa.inspect(op.get_bind()).get_columns("articles")}
    if "last_crawled_at" not in columns:
        op.add_column("articles", sa.Column("last_crawled_at", sa.DateTime(), nullable=True))
    # Old rows stay NULL: their last fetch time is not known reliably.


def downgrade() -> None:
    op.drop_column("articles", "last_crawled_at")
