# backend/tests/test_board_api.py

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
from app.services.dashboard_service import get_active_board_names


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
    session.add(User(username="admin", password_hash=hash_password("admin123"),
                     display_name="管理員", role="admin", is_active=1))
    platform = Platform(name="ptt")
    session.add(platform)
    session.flush()
    b1 = Board(platform_id=platform.id, name="facelift", display_name="醫美整形", is_active=1)
    b2 = Board(platform_id=platform.id, name="MakeUp", display_name="彩妝", is_active=1)
    session.add_all([b1, b2])
    session.flush()
    session.add(Article(unique_id="a1", platform_id=platform.id, board_id=b1.id,
                        title="t", url="u", push_count=1, published_at=datetime.utcnow()))
    session.commit()
    session.close()

    yield TestClient(app), TestSession
    app.dependency_overrides.clear()


def admin_header(c):
    token = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestBoards:
    def test_list_with_counts(self, client):
        c, _ = client
        boards = c.get("/api/admin/boards", headers=admin_header(c)).json()["data"]["boards"]
        by_name = {b["name"]: b for b in boards}
        assert by_name["facelift"]["article_count"] == 1
        assert by_name["MakeUp"]["article_count"] == 0

    def test_add_board(self, client):
        c, _ = client
        resp = c.post("/api/admin/boards", json={"name": "fashion", "display_name": "時尚"}, headers=admin_header(c))
        assert resp.status_code == 200
        assert resp.json()["board"]["name"] == "fashion"

    def test_duplicate_rejected(self, client):
        c, _ = client
        assert c.post("/api/admin/boards", json={"name": "facelift"}, headers=admin_header(c)).status_code == 409

    def test_toggle_active_affects_scheduler_targets(self, client):
        c, TestSession = client
        boards = c.get("/api/admin/boards", headers=admin_header(c)).json()["data"]["boards"]
        makeup_id = next(b["id"] for b in boards if b["name"] == "MakeUp")

        c.patch(f"/api/admin/boards/{makeup_id}", json={"is_active": False}, headers=admin_header(c))

        db = TestSession()
        active = get_active_board_names(db)
        db.close()
        assert "MakeUp" not in active
        assert "facelift" in active

    def test_delete_board_with_articles_blocked(self, client):
        c, _ = client
        boards = c.get("/api/admin/boards", headers=admin_header(c)).json()["data"]["boards"]
        facelift_id = next(b["id"] for b in boards if b["name"] == "facelift")
        assert c.delete(f"/api/admin/boards/{facelift_id}", headers=admin_header(c)).status_code == 409

    def test_delete_empty_board_ok(self, client):
        c, _ = client
        boards = c.get("/api/admin/boards", headers=admin_header(c)).json()["data"]["boards"]
        makeup_id = next(b["id"] for b in boards if b["name"] == "MakeUp")
        assert c.delete(f"/api/admin/boards/{makeup_id}", headers=admin_header(c)).status_code == 200

    def test_boards_admin_only(self, client):
        c, _ = client
        assert c.get("/api/admin/boards").status_code in (401, 403)
