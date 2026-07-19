# backend/tests/test_auth_api.py

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
    # 說明：
    # 每個測試用獨立的 SQLite in-memory 資料庫，
    # 透過 dependency override 換掉 get_db，不碰真正的資料庫。
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

    # 登入 rate limiter 是全域狀態，先清空避免測試之間互相影響。
    login_rate_limiter._hits.clear()

    session = TestSession()
    session.add(User(
        username="tester",
        password_hash=hash_password("secret123"),
        display_name="測試帳號",
        role="user",
        is_active=1,
    ))
    session.commit()
    session.close()

    yield TestClient(app)

    app.dependency_overrides.clear()


def login(client, username="tester", password="secret123"):
    return client.post("/api/auth/login", json={
        "username": username,
        "password": password,
    })


class TestLoginApi:
    def test_login_success_returns_token_and_user(self, client):
        response = login(client)

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["user"]["username"] == "tester"
        assert body["user"]["display_name"] == "測試帳號"

    def test_wrong_password_rejected(self, client):
        response = login(client, password="wrong")

        assert response.status_code == 401

    def test_me_requires_token(self, client):
        assert client.get("/api/auth/me").status_code in (401, 403)

    def test_me_with_token(self, client):
        token = login(client).json()["access_token"]

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["user"]["username"] == "tester"


class TestChangePasswordApi:
    def test_requires_token(self, client):
        response = client.post("/api/auth/change-password", json={
            "old_password": "secret123",
            "new_password": "newpass456",
        })

        assert response.status_code in (401, 403)

    def test_wrong_old_password_rejected(self, client):
        token = login(client).json()["access_token"]

        response = client.post(
            "/api/auth/change-password",
            json={"old_password": "wrong", "new_password": "newpass456"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    def test_short_new_password_rejected(self, client):
        token = login(client).json()["access_token"]

        response = client.post(
            "/api/auth/change-password",
            json={"old_password": "secret123", "new_password": "abc"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422

    def test_full_change_password_flow(self, client):
        token = login(client).json()["access_token"]

        response = client.post(
            "/api/auth/change-password",
            json={"old_password": "secret123", "new_password": "newpass456"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        # 舊密碼不能再登入，新密碼可以。
        assert login(client, password="secret123").status_code == 401
        assert login(client, password="newpass456").status_code == 200
