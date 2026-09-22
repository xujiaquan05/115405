# backend/tests/test_referential_integrity.py

"""帳號刪除時，相關資料該走的路各不相同。

背景：查 information_schema 時發現 `watch_keywords.user_id` 與 `alerts.user_id`
在模型裡宣告了 ondelete="CASCADE"，資料庫卻根本沒有這個外鍵——
這些欄位是在資料表已存在後用 `ALTER TABLE ... ADD COLUMN` 補的，
ADD COLUMN 只加欄位不建外鍵，而 `create_all` 只建立缺少的資料表。
結果是刪除帳號會留下孤兒資料，而系統手冊還寫著它會被清除。

這些測試開啟 SQLite 的外鍵強制（預設是關閉的），
驗證模型宣告的刪除規則確實是我們要的行為。
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.database_models import Alert, AuditLog, Plan, User, WatchKeyword


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    # SQLite 預設不強制外鍵，不開這個 pragma 的話本檔所有測試都會假性通過。
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def user(db):
    db.add(Plan(code="free", display_name="免費方案"))
    db.commit()

    account = User(
        username="someone",
        password_hash="x",
        role="user",
        is_active=1,
        plan_code="free",
    )
    db.add(account)
    db.commit()

    return account


class TestPersonalDataFollowsTheAccount:
    def test_watch_keywords_are_removed_with_the_account(self, db, user):
        db.add(WatchKeyword(user_id=user.id, keyword="音波", days=30, enabled=1))
        db.commit()

        db.delete(user)
        db.commit()

        assert db.query(WatchKeyword).count() == 0

    def test_alerts_are_removed_with_the_account(self, db, user):
        db.add(Alert(user_id=user.id, keyword="音波", level="warning", title="負面聲量上升"))
        db.commit()

        db.delete(user)
        db.commit()

        assert db.query(Alert).count() == 0


class TestAuditTrailSurvivesTheAccount:
    """稽核紀錄不能跟著帳號消失——帳號被刪掉正是最需要查紀錄的時候。"""

    def test_the_record_stays_and_only_the_link_is_cleared(self, db, user):
        db.add(AuditLog(actor_id=user.id, actor_username="someone", action="login_failed"))
        db.commit()

        db.delete(user)
        db.commit()

        remaining = db.query(AuditLog).one()
        assert remaining.actor_id is None
        # 使用者名稱另存一份，連結斷了仍看得出當初是誰。
        assert remaining.actor_username == "someone"


class TestPlanInUseCannotBeDeleted:
    def test_deleting_a_plan_with_accounts_on_it_is_refused(self, db, user):
        plan = db.query(Plan).filter(Plan.code == "free").one()
        db.delete(plan)

        # CASCADE 會連帶刪掉使用者，SET NULL 會讓帳號變成沒有方案；
        # 兩者都比「不准刪」糟。
        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()

    def test_an_unused_plan_can_still_be_deleted(self, db, user):
        db.add(Plan(code="legacy", display_name="舊方案"))
        db.commit()

        db.delete(db.query(Plan).filter(Plan.code == "legacy").one())
        db.commit()

        assert db.query(Plan).count() == 1


class TestModelsDeclareWhatTheDatabaseEnforces:
    """模型與資料庫對不上，正是這次問題的起點。"""

    @pytest.mark.parametrize(
        "table,column,expected",
        [
            ("watch_keywords", "user_id", "CASCADE"),
            ("alerts", "user_id", "CASCADE"),
            ("audit_logs", "actor_id", "SET NULL"),
            ("users", "plan_code", "RESTRICT"),
        ],
    )
    def test_delete_rule_is_declared(self, table, column, expected):
        target = Base.metadata.tables[table].columns[column]
        rules = {fk.ondelete for fk in target.foreign_keys}

        assert rules == {expected}
