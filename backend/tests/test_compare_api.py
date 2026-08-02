# backend/tests/test_compare_api.py

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.database_models import Article, Board, Platform


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

    session = TestSession()
    platform = Platform(name="ptt")
    session.add(platform)
    session.flush()
    board = Board(platform_id=platform.id, name="facelift")
    session.add(board)
    session.flush()

    def add(keyword, sentiment, n, idx0):
        for i in range(n):
            session.add(Article(
                unique_id=f"{keyword}-{sentiment}-{idx0 + i}",
                platform_id=platform.id, board_id=board.id,
                title=f"{keyword} 討論 {i}", content=f"{keyword} 內容",
                url=f"http://x/{keyword}/{sentiment}/{idx0 + i}",
                push_count=8, sentiment=sentiment,
                published_at=datetime.utcnow(),
            ))

    # A：多正面；B：多負面
    add("玻尿酸", "positive", 8, 0)
    add("玻尿酸", "negative", 2, 100)
    add("肉毒", "negative", 7, 0)
    add("肉毒", "positive", 3, 100)
    session.commit()
    session.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


class TestCompare:
    def test_compare_two_keywords(self, client):
        resp = client.get("/api/analysis/compare", params={
            "keywords": ["玻尿酸", "肉毒"], "days": 30,
        })
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        assert len(results) == 2

        by_kw = {r["keyword"]: r for r in results}
        # 玻尿酸 多正面 → 分數應高於 肉毒
        assert by_kw["玻尿酸"]["sentiment_score"] > by_kw["肉毒"]["sentiment_score"]
        assert by_kw["玻尿酸"]["article_count"] == 10
        assert by_kw["肉毒"]["negative"] > by_kw["玻尿酸"]["negative"]

    def test_dedupe_and_limit(self, client):
        resp = client.get("/api/analysis/compare", params={
            "keywords": ["玻尿酸", "玻尿酸", "肉毒"], "days": 30,
        })
        results = resp.json()["data"]["results"]
        assert len(results) == 2  # 去重

    def test_empty_keywords_rejected(self, client):
        resp = client.get("/api/analysis/compare", params={"keywords": ["  "], "days": 30})
        assert resp.status_code == 400
