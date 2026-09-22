"""add the user foreign keys the schema was missing, drop a dead column

Revision ID: e4f70c2a9d18
Revises: c3e8a91d7b45
Create Date: 2026-09-23 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e4f70c2a9d18'
down_revision: Union[str, Sequence[str], None] = 'c3e8a91d7b45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 要建立的外鍵：(約束名稱, 子表, 子欄位, 父表, 父欄位, 刪除規則)
FOREIGN_KEYS = [
    # 個人化設定：帳號刪除時一併清掉。模型本來就宣告 CASCADE，
    # 只是資料庫沒有跟著建立（欄位是用 ADD COLUMN 補的，不會帶外鍵）。
    ("fk_watch_keywords_user_id", "watch_keywords", "user_id", "users", "id", "CASCADE"),
    ("fk_alerts_user_id", "alerts", "user_id", "users", "id", "CASCADE"),

    # 稽核紀錄刻意用 SET NULL 而非 CASCADE：
    # 稽核的用途就是在事後追查「誰做了什麼」，帳號被刪掉正是最需要留下紀錄的時候。
    # actor_username 已另存一份使用者名稱，連結斷了仍看得出當初是誰。
    ("fk_audit_logs_actor_id", "audit_logs", "actor_id", "users", "id", "SET NULL"),

    # 方案代碼用 RESTRICT：還有帳號在用的方案不該被刪掉。
    # 用 CASCADE 會連帶刪掉使用者，用 SET NULL 會讓帳號變成沒有方案。
    ("fk_users_plan_code", "users", "plan_code", "plans", "code", "RESTRICT"),
]


def upgrade() -> None:
    """補上四組外鍵，並刪掉一個已無人讀寫的欄位。

    為什麼這些外鍵原本不存在？
    這些欄位都是在資料表已經建立之後才加上的，而當時是用
    `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`——ADD COLUMN 只加欄位、不建外鍵，
    startup 的 create_all 又只會建立「缺少的資料表」，不會在既有資料表上補約束。
    結果是模型裡宣告了 ondelete="CASCADE"，資料庫卻完全沒有這個約束：
    刪除帳號時，它的監測關鍵字與預警會變成孤兒資料。

    執行前已確認資料庫中沒有孤兒列，因此建立約束不會失敗。
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for name, table, column, ref_table, ref_column, ondelete in FOREIGN_KEYS:
        existing = {fk.get("name") for fk in inspector.get_foreign_keys(table)}

        # 已經有了就跳過：開發機可能已用其他方式補過。
        if name in existing:
            continue

        op.create_foreign_key(
            name, table, ref_table, [column], [ref_column], ondelete=ondelete
        )

    # analysis_results.user_id 是拆出 analysis_history 時留下的殘骸：
    # 程式已不再讀寫它，資料庫裡也全部是 NULL，但索引仍在每次寫入時被維護。
    columns = {col["name"] for col in inspector.get_columns("analysis_results")}

    if "user_id" in columns:
        indexes = {idx["name"] for idx in inspector.get_indexes("analysis_results")}

        if "ix_analysis_results_user_id" in indexes:
            op.drop_index("ix_analysis_results_user_id", table_name="analysis_results")

        op.drop_column("analysis_results", "user_id")


def downgrade() -> None:
    op.add_column("analysis_results", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_analysis_results_user_id", "analysis_results", ["user_id"], unique=False
    )

    for name, table, _column, _ref_table, _ref_column, _ondelete in reversed(FOREIGN_KEYS):
        op.drop_constraint(name, table, type_="foreignkey")
