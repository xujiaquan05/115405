"""make the database agree with the models on three columns and one delete rule

Revision ID: a7d31c6f0e92
Revises: f1a92b3c4d56
Create Date: 2026-10-03 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7d31c6f0e92'
down_revision: Union[str, Sequence[str], None] = 'f1a92b3c4d56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 模型宣告 NOT NULL、資料庫卻允許 NULL 的三個欄位。
# (資料表, 欄位, 型別, 伺服器預設值, 補值用的字面值)
NOT_NULL_COLUMNS = [
    ("boards", "is_active", sa.Integer(), "1", "1"),
    ("users", "plan_code", sa.String(length=20), "'free'::character varying", "'free'"),
    ("users", "failed_login_count", sa.Integer(), "0", "0"),
]

BOARDS_FK = "boards_platform_id_fkey"


def upgrade() -> None:
    """讓資料庫與 ORM 模型對齊。

    這些差異怎麼來的？
    資料庫最早是由 database/init.sql 手寫建立，模型則另外寫在
    app/models/database_models.py，兩份來源沒有互相對照；之後又有三個欄位是用
    app/core/startup.py 的 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ... DEFAULT x`
    補上的。ADD COLUMN 沒有寫 NOT NULL，PostgreSQL 就建成可空欄位，而模型那邊
    照著原意寫了 nullable=False。startup 的 create_all 只建立「缺少的資料表」，
    不會修改既有資料表，所以兩邊一路漂移都沒有東西會發現。

    差異的實際影響在測試：tests/ 以 Base.metadata.create_all 由模型建表，
    得到的綱要比正式資料庫嚴格，等於測試跑在另一套綱要上。

    本次把資料庫改成與模型一致，模型本身不需要改動。
    """
    # 1. 先補值再加限制。本機這三欄目前都沒有 NULL，但其他環境不一定，
    #    少了這步在別台機器執行會直接失敗。
    for table, column, _type, _default, literal in NOT_NULL_COLUMNS:
        op.execute(
            f"UPDATE {table} SET {column} = {literal} WHERE {column} IS NULL"
        )

    for table, column, type_, server_default, _literal in NOT_NULL_COLUMNS:
        op.alter_column(
            table, column,
            existing_type=type_,
            existing_server_default=sa.text(server_default),
            nullable=False,
        )

    # 2. boards.platform_id 的刪除規則：資料庫是 ON DELETE CASCADE（來自 init.sql
    #    第33行），模型的 ForeignKey 沒有寫 ondelete，等同 NO ACTION。
    #
    #    這次改資料庫、不改模型，理由是 NO ACTION 才與同樣指向 platforms 的
    #    articles 與 crawl_logs 一致。CASCADE 是三者中唯一會「安靜刪掉資料」的：
    #    看板上帶有 is_active 等爬取設定，不該因為刪平台而無聲消失。
    #    實務上目前也不會觸發——程式沒有任何地方刪除平台，而且 articles 指向
    #    platforms 是 NO ACTION，有文章的平台本來就刪不掉。
    op.drop_constraint(BOARDS_FK, "boards", type_="foreignkey")
    op.create_foreign_key(BOARDS_FK, "boards", "platforms", ["platform_id"], ["id"])


def downgrade() -> None:
    """還原成遷移前的狀態：三欄恢復可空，看板外鍵恢復 CASCADE。"""
    op.drop_constraint(BOARDS_FK, "boards", type_="foreignkey")
    op.create_foreign_key(
        BOARDS_FK, "boards", "platforms", ["platform_id"], ["id"], ondelete="CASCADE"
    )

    for table, column, type_, server_default, _literal in NOT_NULL_COLUMNS:
        op.alter_column(
            table, column,
            existing_type=type_,
            existing_server_default=sa.text(server_default),
            nullable=True,
        )
