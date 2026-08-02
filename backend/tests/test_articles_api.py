# backend/tests/test_articles_api.py

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
    session.add(Article(
        id=1, unique_id="u1", platform_id=platform.id, board_id=board.id,
        title="[心得] 玻尿酸心得", content="完整內文\n第二段", url="http://ptt/x1",
        push_count=45, sentiment="positive", published_at=datetime(2026, 7, 20, 14, 0, 0),
    ))
    session.commit()
    session.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


class TestArticleDetail:
    def test_get_existing_article(self, client):
        resp = client.get("/api/articles/1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "[心得] 玻尿酸心得"
        assert data["content"] == "完整內文\n第二段"
        assert data["board"] == "facelift"
        assert data["sentiment"] == "positive"
        assert data["push_count"] == 45

    def test_missing_article_returns_404(self, client):
        assert client.get("/api/articles/999").status_code == 404
