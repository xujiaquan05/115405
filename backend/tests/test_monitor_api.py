# backend/tests/test_monitor_api.py

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.database_models import Article, Board, Platform, User
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
    platform = Platform(name="ptt")
    session.add(platform)
    session.flush()
    board = Board(platform_id=platform.id, name="facelift")
    session.add(board)
    session.flush()
    # 8 篇負面 + 2 篇正面 → 負面 80% → 應觸發 critical。
    for i in range(10):
        session.add(Article(
            unique_id=f"u{i}",
            platform_id=platform.id,
            board_id=board.id,
            title=f"玻尿酸 {i}",
            content="內容",
            url=f"http://x/{i}",
            push_count=5,
            sentiment="negative" if i < 8 else "positive",
            published_at=datetime.utcnow(),
        ))
    session.commit()
    session.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


def admin_header(client):
    token = client.post("/api/auth/login", json={
        "username": "admin", "password": "admin123",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestWatchKeywords:
    def test_add_and_list(self, client):
        h = admin_header(client)
        resp = client.post("/api/monitor/keywords", json={"keyword": "玻尿酸", "days": 30}, headers=h)
        assert resp.status_code == 200

        keywords = client.get("/api/monitor/keywords").json()["data"]["keywords"]
        assert any(k["keyword"] == "玻尿酸" for k in keywords)

    def test_add_requires_login(self, client):
        resp = client.post("/api/monitor/keywords", json={"keyword": "肉毒", "days": 7})
        assert resp.status_code in (401, 403)

    def test_duplicate_rejected(self, client):
        h = admin_header(client)
        client.post("/api/monitor/keywords", json={"keyword": "玻尿酸", "days": 30}, headers=h)
        dup = client.post("/api/monitor/keywords", json={"keyword": "玻尿酸", "days": 30}, headers=h)
        assert dup.status_code == 409


class TestAlertsFlow:
    def test_check_creates_alert_and_unread(self, client):
        h = admin_header(client)
        client.post("/api/monitor/keywords", json={"keyword": "玻尿酸", "days": 30}, headers=h)

        check = client.post("/api/monitor/alerts/check", headers=h)
        assert check.status_code == 200
        assert check.json()["created_count"] == 1

        listing = client.get("/api/monitor/alerts").json()["data"]
        assert listing["unread_count"] == 1
        assert listing["alerts"][0]["level"] == "critical"

    def test_mark_read_clears_unread(self, client):
        h = admin_header(client)
        client.post("/api/monitor/keywords", json={"keyword": "玻尿酸", "days": 30}, headers=h)
        client.post("/api/monitor/alerts/check", headers=h)

        alert_id = client.get("/api/monitor/alerts").json()["data"]["alerts"][0]["id"]
        client.post(f"/api/monitor/alerts/{alert_id}/read", headers=h)

        assert client.get("/api/monitor/alerts").json()["data"]["unread_count"] == 0

    def test_run_now_requires_admin(self, client):
        # 建一個一般使用者
        h = admin_header(client)
        client.post("/api/admin/users", json={"username": "u1", "password": "userpass1", "role": "user"}, headers=h)
        user_token = client.post("/api/auth/login", json={"username": "u1", "password": "userpass1"}).json()["access_token"]

        resp = client.post("/api/monitor/run-now", headers={"Authorization": f"Bearer {user_token}"})
        assert resp.status_code == 403
