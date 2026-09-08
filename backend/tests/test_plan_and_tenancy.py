# backend/tests/test_plan_and_tenancy.py

"""多租戶隔離與方案額度。

這兩件事是收費前的前提：客戶不能看到彼此的資料，
額度也必須真的擋得住，否則方案只是說明文字。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.database_models import Plan, User
from app.routers.auth import login_rate_limiter
from app.services.auth_service import hash_password

PLANS = [
    dict(code="free", display_name="免費版", max_watch_keywords=1, max_history_days=7,
         allow_all_platforms=0, monthly_qa_quota=0, allow_export=0, sort_order=0),
    dict(code="pro", display_name="專業版", max_watch_keywords=5, max_history_days=90,
         allow_all_platforms=1, monthly_qa_quota=100, allow_export=1, sort_order=1),
]


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
    login_rate_limiter._hits.clear()

    session = TestSession()
    session.add_all([Plan(**spec) for spec in PLANS])
    # 兩位一般使用者（非管理員，才會受額度限制）
    for name, plan in (("alice", "free"), ("bob", "pro")):
        session.add(User(username=name, password_hash=hash_password("pw123456"),
                         display_name=name, role="user", is_active=1, plan_code=plan))
    session.commit()
    session.close()

    yield TestClient(app), TestSession
    app.dependency_overrides.clear()


def header(c, username):
    token = c.post("/api/auth/login", json={"username": username, "password": "pw123456"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestTenantIsolation:
    def test_users_only_see_their_own_keywords(self, client):
        c, _ = client
        alice, bob = header(c, "alice"), header(c, "bob")

        c.post("/api/monitor/keywords", json={"keyword": "A診所", "days": 7}, headers=alice)
        c.post("/api/monitor/keywords", json={"keyword": "B診所", "days": 7}, headers=bob)

        alice_list = c.get("/api/monitor/keywords", headers=alice).json()["data"]["keywords"]
        bob_list = c.get("/api/monitor/keywords", headers=bob).json()["data"]["keywords"]

        assert [k["keyword"] for k in alice_list] == ["A診所"]
        assert [k["keyword"] for k in bob_list] == ["B診所"]

    def test_same_keyword_allowed_for_different_users(self, client):
        """不同客戶監控同一個品牌名稱是正常情境，不可視為重複。"""
        c, _ = client

        first = c.post("/api/monitor/keywords", json={"keyword": "醫美", "days": 7}, headers=header(c, "alice"))
        second = c.post("/api/monitor/keywords", json={"keyword": "醫美", "days": 7}, headers=header(c, "bob"))

        assert first.status_code == 200
        assert second.status_code == 200

    def test_cannot_delete_another_users_keyword(self, client):
        c, _ = client
        alice = header(c, "alice")

        created = c.post("/api/monitor/keywords", json={"keyword": "A診所", "days": 7}, headers=alice)
        keyword_id = created.json()["keyword"]["id"]

        assert c.delete(f"/api/monitor/keywords/{keyword_id}", headers=header(c, "bob")).status_code == 404

    def test_guest_sees_no_alerts(self, client):
        c, _ = client

        data = c.get("/api/monitor/alerts").json()["data"]

        assert data["alerts"] == []
        assert data["unread_count"] == 0


class TestPlanQuota:
    def test_free_plan_limited_to_one_keyword(self, client):
        c, _ = client
        alice = header(c, "alice")

        assert c.post("/api/monitor/keywords", json={"keyword": "第一組", "days": 7}, headers=alice).status_code == 200

        blocked = c.post("/api/monitor/keywords", json={"keyword": "第二組", "days": 7}, headers=alice)
        assert blocked.status_code == 403
        assert "免費版" in blocked.json()["detail"]

    def test_pro_plan_allows_more(self, client):
        c, _ = client
        bob = header(c, "bob")

        for index in range(5):
            assert c.post("/api/monitor/keywords", json={"keyword": f"品牌{index}", "days": 7},
                          headers=bob).status_code == 200

        assert c.post("/api/monitor/keywords", json={"keyword": "第六組", "days": 7},
                      headers=bob).status_code == 403

    def test_free_plan_cannot_export(self, client):
        c, _ = client

        resp = c.get("/api/export/articles.xlsx", headers=header(c, "alice"))

        assert resp.status_code == 403
        assert "匯出" in resp.json()["detail"]

    def test_plan_status_reports_usage(self, client):
        c, _ = client
        alice = header(c, "alice")
        c.post("/api/monitor/keywords", json={"keyword": "A診所", "days": 7}, headers=alice)

        plan = c.get("/api/monitor/keywords", headers=alice).json()["data"]["plan"]

        assert plan["plan"]["code"] == "free"
        assert plan["usage"]["watch_keywords"] == 1


class TestAdminBypass:
    def test_admin_is_not_limited(self, client):
        """管理員負責維運，不該被自己設定的方案擋住。"""
        c, TestSession = client

        session = TestSession()
        session.add(User(username="root", password_hash=hash_password("pw123456"),
                         display_name="root", role="admin", is_active=1, plan_code="free"))
        session.commit()
        session.close()

        root = header(c, "root")

        for index in range(3):
            assert c.post("/api/monitor/keywords", json={"keyword": f"K{index}", "days": 7},
                          headers=root).status_code == 200


class TestKeywordUpdate:
    """PATCH 端點曾經只寫 dependencies=[Depends(get_current_user)]，
    沒有把使用者綁進參數，導致函式裡的 current_user 未定義而 500。
    這個缺陷是靜態檢查（ruff F821）發現的，測試補上以免再犯。"""

    def test_owner_can_toggle_keyword(self, client):
        c, _ = client
        alice = header(c, "alice")
        created = c.post("/api/monitor/keywords", json={"keyword": "A診所", "days": 7}, headers=alice)
        keyword_id = created.json()["keyword"]["id"]

        resp = c.patch(f"/api/monitor/keywords/{keyword_id}", json={"enabled": False}, headers=alice)

        assert resp.status_code == 200
        assert resp.json()["keyword"]["enabled"] is False

    def test_cannot_toggle_another_users_keyword(self, client):
        c, _ = client
        created = c.post("/api/monitor/keywords", json={"keyword": "A診所", "days": 7},
                         headers=header(c, "alice"))
        keyword_id = created.json()["keyword"]["id"]

        resp = c.patch(f"/api/monitor/keywords/{keyword_id}", json={"enabled": False},
                       headers=header(c, "bob"))

        assert resp.status_code == 404
