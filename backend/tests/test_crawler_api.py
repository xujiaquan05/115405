# backend/tests/test_crawler_api.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.crawlers.dcard_crawler import DcardCrawler
from app.crawlers.ptt_crawler import PTTCrawler
from app.crawlers.registry import get_crawler
from app.main import app
from app.models.database_models import User
from app.routers.auth import login_rate_limiter
from app.services.auth_service import hash_password


class TestCrawlerRegistry:
    def test_ptt(self):
        assert isinstance(get_crawler("ptt"), PTTCrawler)

    def test_dcard(self):
        assert isinstance(get_crawler("dcard"), DcardCrawler)

    def test_unknown_falls_back_to_ptt(self):
        assert isinstance(get_crawler("weibo"), PTTCrawler)


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
    session.commit()
    session.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


def admin_header(c):
    token = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestDcardCrawlEndpoint:
    def test_requires_login(self, client):
        # 未登入不能觸發爬蟲
        assert client.post("/api/crawler/dcard", params={"board": "makeup"}).status_code in (401, 403)

    def test_invalid_board_rejected(self, client):
        # 不存在的 Dcard 看板 → 400（在排入背景任務前就擋下，不會開瀏覽器）
        resp = client.post("/api/crawler/dcard", params={"board": "no_such_forum"},
                           headers=admin_header(client))
        assert resp.status_code == 400

    def test_rejected_when_dcard_disabled(self, client):
        # 在系統設定關閉 Dcard 後，觸發 /dcard 應回 403（不會開瀏覽器）
        headers = admin_header(client)
        client.put("/api/admin/settings", json={"dcard_crawl_enabled": False}, headers=headers)

        resp = client.post("/api/crawler/dcard", params={"board": "makeup"}, headers=headers)
        assert resp.status_code == 403
