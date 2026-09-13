# backend/tests/test_analysis_history.py

"""分析歷史的租戶隔離。

先前歷史頁直接讀 analysis_results，而那是以 keyword 為鍵的「共用快取」。
造成兩個問題，這裡各有對應的測試：
1. 客戶看得到別人分析過哪些關鍵字（商業資訊外洩）
2. 刪除「自己的紀錄」實際刪掉共用快取，害所有人重付一次 Gemini 費用
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.time_utils import taiwan_now
from app.main import app
from app.models.database_models import AnalysisHistory, AnalysisResult, User
from app.services.auth_service import hash_password

PASSWORD = "Str0ng-Pass-99"


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    session = TestSession()
    for name in ("alice", "bob"):
        session.add(User(username=name, password_hash=hash_password(PASSWORD),
                         display_name=name, role="user", is_active=1))
    session.commit()
    session.close()

    yield TestClient(app), TestSession
    app.dependency_overrides.clear()


def header(c, username):
    token = c.post("/api/auth/login", json={"username": username, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def add_history(TestSession, username, keyword):
    session = TestSession()
    user = session.query(User).filter(User.username == username).one()
    session.add(AnalysisHistory(
        user_id=user.id, keyword=keyword, analysis_type="overview",
        days=30, result_json={"summary": "x"}, created_at=taiwan_now(),
    ))
    session.commit()
    record_id = session.query(AnalysisHistory).filter(
        AnalysisHistory.keyword == keyword).one().id
    session.close()
    return record_id


class TestHistoryIsolation:
    def test_user_only_sees_their_own_analyses(self, client):
        c, TestSession = client
        add_history(TestSession, "alice", "A診所")
        add_history(TestSession, "bob", "B診所")

        keywords = [
            r["keyword"]
            for r in c.get("/api/analysis/history", headers=header(c, "alice")).json()["data"]["records"]
        ]

        assert keywords == ["A診所"]

    def test_history_requires_login(self, client):
        c, _ = client

        assert c.get("/api/analysis/history").status_code in (401, 403)


class TestHistoryDeletion:
    def test_cannot_delete_another_users_record(self, client):
        c, TestSession = client
        record_id = add_history(TestSession, "alice", "A診所")

        resp = c.delete(f"/api/analysis/history/{record_id}", headers=header(c, "bob"))

        assert resp.status_code == 404

    def test_deleting_history_leaves_the_shared_cache_intact(self, client):
        """關鍵：刪自己的紀錄不可以動到共用的 Gemini 快取，
        否則其他客戶下次分析同一關鍵字時要重新付費呼叫。"""
        c, TestSession = client
        record_id = add_history(TestSession, "alice", "A診所")

        session = TestSession()
        session.add(AnalysisResult(
            keyword="A診所", analysis_type="overview", days=30,
            result_json={"summary": "cached"}, expired_at=taiwan_now(),
        ))
        session.commit()
        session.close()

        assert c.delete(f"/api/analysis/history/{record_id}",
                        headers=header(c, "alice")).status_code == 200

        session = TestSession()
        cache_rows = session.query(AnalysisResult).count()
        history_rows = session.query(AnalysisHistory).count()
        session.close()

        assert cache_rows == 1   # 快取還在
        assert history_rows == 0  # 只刪掉歷史


class TestCacheStaysShared:
    def test_analysis_results_has_no_user_column(self):
        """共用快取刻意不分使用者：同一個關鍵字只呼叫一次 Gemini。
        若哪天有人加回 user_id，等於讓每個客戶各自付費重算。"""
        assert not hasattr(AnalysisResult, "user_id")
