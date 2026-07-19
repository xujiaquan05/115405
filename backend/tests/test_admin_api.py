# backend/tests/test_admin_api.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.database_models import User
from app.routers.auth import login_rate_limiter
from app.services.auth_service import hash_password


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
    session.add(User(
        username="admin",
        password_hash=hash_password("admin123"),
        display_name="管理員",
        role="admin",
        is_active=1,
    ))
    session.add(User(
        username="normal",
        password_hash=hash_password("user123"),
        display_name="一般",
        role="user",
        is_active=1,
    ))
    session.commit()
    session.close()

    yield TestClient(app)

    app.dependency_overrides.clear()


def auth_header(client, username, password):
    token = client.post("/api/auth/login", json={
        "username": username,
        "password": password,
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def admin_header(client):
    return auth_header(client, "admin", "admin123")


class TestAdminAccessControl:
    def test_non_admin_forbidden(self, client):
        headers = auth_header(client, "normal", "user123")
        assert client.get("/api/admin/users", headers=headers).status_code == 403

    def test_anonymous_rejected(self, client):
        assert client.get("/api/admin/users").status_code in (401, 403)

    def test_admin_can_list(self, client):
        response = client.get("/api/admin/users", headers=admin_header(client))
        assert response.status_code == 200
        usernames = [u["username"] for u in response.json()["data"]["users"]]
        assert "admin" in usernames and "normal" in usernames

    def test_list_includes_stats(self, client):
        stats = client.get("/api/admin/users", headers=admin_header(client)).json()["data"]["stats"]
        assert stats["total"] == 2
        assert stats["admins"] == 1
        assert stats["active"] == 2


class TestLastLoginAndAudit:
    def test_last_login_recorded(self, client):
        # 登入前 last_login_at 是 None，登入後應被填上。
        before = client.get("/api/admin/users", headers=admin_header(client)).json()["data"]["users"]
        normal_before = next(u for u in before if u["username"] == "normal")
        assert normal_before["last_login_at"] is None

        auth_header(client, "normal", "user123")

        after = client.get("/api/admin/users", headers=admin_header(client)).json()["data"]["users"]
        normal_after = next(u for u in after if u["username"] == "normal")
        assert normal_after["last_login_at"] is not None

    def test_stats_logged_this_week(self, client):
        auth_header(client, "normal", "user123")
        stats = client.get("/api/admin/users", headers=admin_header(client)).json()["data"]["stats"]
        # admin（剛剛登入）與 normal 都算本週登入。
        assert stats["logged_this_week"] >= 2

    def test_audit_log_records_create(self, client):
        client.post(
            "/api/admin/users",
            json={"username": "editor", "password": "editor123"},
            headers=admin_header(client),
        )

        logs = client.get("/api/admin/audit-logs", headers=admin_header(client)).json()["data"]["logs"]
        assert any(
            log["action"] == "create_user" and log["target_username"] == "editor"
            for log in logs
        )
        assert logs[0]["actor_username"] == "admin"

    def test_audit_log_records_delete(self, client):
        users = client.get("/api/admin/users", headers=admin_header(client)).json()["data"]["users"]
        normal_id = next(u["id"] for u in users if u["username"] == "normal")
        client.delete(f"/api/admin/users/{normal_id}", headers=admin_header(client))

        logs = client.get("/api/admin/audit-logs", headers=admin_header(client)).json()["data"]["logs"]
        assert any(log["action"] == "delete_user" and log["target_username"] == "normal" for log in logs)

    def test_audit_logs_admin_only(self, client):
        headers = auth_header(client, "normal", "user123")
        assert client.get("/api/admin/audit-logs", headers=headers).status_code == 403


class TestCreateUser:
    def test_create_success(self, client):
        response = client.post(
            "/api/admin/users",
            json={"username": "editor", "password": "editor123", "role": "user"},
            headers=admin_header(client),
        )
        assert response.status_code == 200
        assert response.json()["user"]["username"] == "editor"
        # 新帳號可以立即登入。
        assert client.post("/api/auth/login", json={
            "username": "editor", "password": "editor123",
        }).status_code == 200

    def test_duplicate_username_rejected(self, client):
        response = client.post(
            "/api/admin/users",
            json={"username": "normal", "password": "another123"},
            headers=admin_header(client),
        )
        assert response.status_code == 409

    def test_short_password_rejected(self, client):
        response = client.post(
            "/api/admin/users",
            json={"username": "shorty", "password": "abc"},
            headers=admin_header(client),
        )
        assert response.status_code == 422

    def test_invalid_role_rejected(self, client):
        response = client.post(
            "/api/admin/users",
            json={"username": "weird", "password": "weird123", "role": "superuser"},
            headers=admin_header(client),
        )
        assert response.status_code == 400


class TestUpdateUser:
    def _normal_id(self, client):
        users = client.get("/api/admin/users", headers=admin_header(client)).json()["data"]["users"]
        return next(u["id"] for u in users if u["username"] == "normal")

    def _admin_id(self, client):
        users = client.get("/api/admin/users", headers=admin_header(client)).json()["data"]["users"]
        return next(u["id"] for u in users if u["username"] == "admin")

    def test_promote_and_deactivate_other_user(self, client):
        normal_id = self._normal_id(client)

        promote = client.patch(
            f"/api/admin/users/{normal_id}",
            json={"role": "admin", "is_active": False},
            headers=admin_header(client),
        )
        assert promote.status_code == 200
        assert promote.json()["user"]["role"] == "admin"
        assert promote.json()["user"]["is_active"] is False

    def test_admin_cannot_demote_self(self, client):
        admin_id = self._admin_id(client)
        response = client.patch(
            f"/api/admin/users/{admin_id}",
            json={"role": "user"},
            headers=admin_header(client),
        )
        assert response.status_code == 400

    def test_admin_cannot_deactivate_self(self, client):
        admin_id = self._admin_id(client)
        response = client.patch(
            f"/api/admin/users/{admin_id}",
            json={"is_active": False},
            headers=admin_header(client),
        )
        assert response.status_code == 400

    def test_reset_password(self, client):
        normal_id = self._normal_id(client)
        response = client.patch(
            f"/api/admin/users/{normal_id}",
            json={"new_password": "reset123"},
            headers=admin_header(client),
        )
        assert response.status_code == 200
        assert client.post("/api/auth/login", json={
            "username": "normal", "password": "reset123",
        }).status_code == 200

    def test_deactivated_user_cannot_login(self, client):
        normal_id = self._normal_id(client)
        client.patch(
            f"/api/admin/users/{normal_id}",
            json={"is_active": False},
            headers=admin_header(client),
        )
        assert client.post("/api/auth/login", json={
            "username": "normal", "password": "user123",
        }).status_code == 401


class TestDeleteUser:
    def test_delete_other_user(self, client):
        users = client.get("/api/admin/users", headers=admin_header(client)).json()["data"]["users"]
        normal_id = next(u["id"] for u in users if u["username"] == "normal")

        response = client.delete(f"/api/admin/users/{normal_id}", headers=admin_header(client))
        assert response.status_code == 200

        remaining = client.get("/api/admin/users", headers=admin_header(client)).json()["data"]["users"]
        assert all(u["username"] != "normal" for u in remaining)

    def test_admin_cannot_delete_self(self, client):
        users = client.get("/api/admin/users", headers=admin_header(client)).json()["data"]["users"]
        admin_id = next(u["id"] for u in users if u["username"] == "admin")

        response = client.delete(f"/api/admin/users/{admin_id}", headers=admin_header(client))
        assert response.status_code == 400
