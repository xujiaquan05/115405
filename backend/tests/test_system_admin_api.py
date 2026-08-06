# backend/tests/test_system_admin_api.py

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
    session.add(User(username="admin", password_hash=hash_password("admin123"),
                     display_name="管理員", role="admin", is_active=1))
    session.add(User(username="normal", password_hash=hash_password("user123"),
                     display_name="一般", role="user", is_active=1))
    session.commit()
    session.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


def auth_header(client, username, password):
    token = client.post("/api/auth/login", json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestSystemOverview:
    def test_overview_admin_only(self, client):
        assert client.get("/api/admin/system-overview").status_code in (401, 403)
        normal = auth_header(client, "normal", "user123")
        assert client.get("/api/admin/system-overview", headers=normal).status_code == 403

    def test_overview_shape(self, client):
        resp = client.get("/api/admin/system-overview", headers=auth_header(client, "admin", "admin123"))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["database"] == "connected"
        assert "articles" in data and "scheduler" in data and "users" in data
        assert data["users"]["total"] == 2


class TestSettingsApi:
    def test_get_defaults(self, client):
        resp = client.get("/api/admin/settings", headers=auth_header(client, "admin", "admin123"))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["alert_warning_negative"] == 25.0
        assert data["auto_crawl_hour"] == 3

    def test_update_settings(self, client):
        h = auth_header(client, "admin", "admin123")
        resp = client.put("/api/admin/settings", json={
            "alert_warning_negative": 30,
            "auto_crawl_hour": 8,
        }, headers=h)
        assert resp.status_code == 200
        assert resp.json()["data"]["alert_warning_negative"] == 30.0
        assert resp.json()["data"]["auto_crawl_hour"] == 8

        # 讀回來確認有存
        again = client.get("/api/admin/settings", headers=h).json()["data"]
        assert again["auto_crawl_hour"] == 8

    def test_update_requires_admin(self, client):
        normal = auth_header(client, "normal", "user123")
        assert client.put("/api/admin/settings", json={"auto_crawl_hour": 5}, headers=normal).status_code == 403

    def test_empty_update_rejected(self, client):
        h = auth_header(client, "admin", "admin123")
        assert client.put("/api/admin/settings", json={}, headers=h).status_code == 400
