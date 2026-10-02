"""Regressions for file exposure, production setup, crawling and cache isolation."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from runpy import run_path
from threading import Barrier

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.core.database import Base
from app.core.startup import _seed_admin_user
from app.core.time_utils import taiwan_now
from app.models.database_models import ArticleChunk, Comment, SystemLock, User
from app.services import lock_service, rag_service
from app.services.article_service import create_article, save_comments
from app.services.auth_service import verify_password


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def test_static_files_are_confined_to_public_directory(tmp_path, monkeypatch):
    public = tmp_path / "dist"
    public.mkdir()
    (public / "index.html").write_text("SPA", encoding="utf-8")
    (public / "favicon.svg").write_text("safe asset", encoding="utf-8")
    outside = tmp_path / "private.txt"
    outside.write_text("private marker", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", public)
    client = TestClient(main.app)
    assert client.get("/favicon.svg").text == "safe asset"
    assert client.get("/dashboard").text == "SPA"
    assert client.get("/%2e%2e/private.txt").status_code == 404
    with pytest.raises(HTTPException) as error:
        main.serve_spa(str(outside))
    assert error.value.status_code == 404


def test_static_symlinks_cannot_escape_public_directory(tmp_path, monkeypatch):
    public = tmp_path / "dist"
    public.mkdir()
    outside = tmp_path / "private.txt"
    outside.write_text("private marker", encoding="utf-8")
    try:
        (public / "link.txt").symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks requires additional privileges on this host")
    monkeypatch.setattr(main, "FRONTEND_DIST", public)
    assert TestClient(main.app).get("/link.txt").status_code == 404


@pytest.mark.parametrize("password", [None, "", "admin123", "password123", "short", "change_me_admin_password"])
def test_production_rejects_missing_or_weak_initial_password(db, monkeypatch, password):
    monkeypatch.setenv("APP_ENV", "production")
    if password is None:
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("ADMIN_PASSWORD", password)
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        _seed_admin_user(db)
    assert db.query(User).count() == 0


def test_valid_initial_password_is_hashed_and_existing_admin_is_preserved(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_PASSWORD", "Sufficient-length-5948!")
    _seed_admin_user(db)
    db.commit()
    user = db.query(User).one()
    assert verify_password("Sufficient-length-5948!", user.password_hash)
    monkeypatch.delenv("ADMIN_PASSWORD")
    _seed_admin_user(db)
    assert db.query(User).count() == 1


def test_development_can_still_bootstrap_default_admin(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    _seed_admin_user(db)
    db.commit()
    assert verify_password("admin123", db.query(User).one().password_hash)


def test_recrawl_updates_article_and_invalidates_old_analysis(db):
    data = dict(unique_id="review-article", platform_name="ptt", board_name="BeautySalon",
                author_username="tester", title="Original", content="Old text", url="https://example.test/a")
    article, _ = create_article(db, **data, push_count=1)
    article.sentiment = "positive"
    db.add(ArticleChunk(article_id=article.id, chunk_index=0, content="Old text",
                        vector=b"old", model="test", dimensions=1))
    db.commit()
    previous_time = article.last_crawled_at
    updated, is_new = create_article(db, **{**data, "content": "Changed text"}, push_count=50)
    assert not is_new
    assert updated.id == article.id
    assert updated.content == "Changed text"
    assert updated.push_count == 50
    assert updated.last_crawled_at >= previous_time
    assert updated.sentiment is None
    assert db.query(ArticleChunk).count() == 0
    updated.sentiment = "negative"
    db.commit()
    published_at = updated.published_at
    updated, _ = create_article(db, **{**data, "content": ""}, push_count=51)
    assert updated.content == "Changed text"
    assert updated.sentiment == "negative"
    assert updated.published_at == published_at


def test_comments_merge_partial_snapshots_and_preserve_repetitions(db):
    article, _ = create_article(db, "comment-review", "ptt", "BeautySalon", "tester",
                                "Title", "Body", "https://example.test/a")
    assert save_comments(db, article, ["A", "B", "B"]) == 3
    first = db.query(Comment).order_by(Comment.floor).first()
    first.sentiment = "positive"
    db.commit()
    assert save_comments(db, article, ["B", "B", "C"]) == 1
    assert save_comments(db, article, ["A", "B", "B", "C"]) == 0
    assert save_comments(db, article, ["A"]) == 0
    assert [r.content for r in db.query(Comment).order_by(Comment.floor)] == ["A", "B", "B", "C"]
    assert first.sentiment == "positive"


def test_context_changes_regenerate_answer(monkeypatch):
    monkeypatch.setattr(rag_service, "get_cache", lambda key: store.get(key))
    store = {}
    monkeypatch.setattr(rag_service, "set_cache", lambda key, data, minutes: store.update({key: data}))
    monkeypatch.setattr(rag_service, "generate_dashboard_context_answer",
                        lambda question, context, history: {"answer": str(context["overview"]["total"])})
    context = {"keyword": "review", "days": 30, "overview": {"total": 1}}
    assert rag_service.answer_question(None, "How many?", context)["answer"] == "1"
    context["overview"]["total"] = 999
    result = rag_service.answer_question(None, "How many?", context)
    assert result["answer"] == "999"
    assert result["cached"] is False


def test_cache_preserves_role_and_message_boundaries():
    key = rag_service._qa_cache_key
    assert key("Q", None, [{"role": "user", "content": "A"}]) != key(
        "Q", None, [{"role": "assistant", "content": "A"}])
    assert key("Q", None, [{"role": "user", "content": "A|B"}]) != key(
        "Q", None, [{"role": "user", "content": "A"}, {"role": "user", "content": "B"}])
    assert key("Q", {"days": 30, "keyword": "K"}, None) == key(
        "Q", {"keyword": "K", "days": 30}, None)


def test_expired_owner_cannot_renew_or_delete_replacement(db):
    Session = sessionmaker(bind=db.get_bind())
    assert lock_service.try_acquire(db, "crawler", ttl_minutes=-1)
    original = lock_service.lease_owner(db, "crawler")
    with Session() as replacement:
        assert lock_service.try_acquire(replacement, "crawler")
        assert lock_service.lease_owner(replacement, "crawler") != original
        assert not lock_service.renew(db, "crawler")
        lock_service.release(db, "crawler")
        assert lock_service.is_held(replacement, "crawler")
        lock_service.release(replacement, "crawler")
        assert not lock_service.is_held(replacement, "crawler")


def test_lease_token_can_be_handed_to_background_session(db):
    assert lock_service.try_acquire(db, "crawler")
    token = lock_service.lease_owner(db, "crawler")
    with sessionmaker(bind=db.get_bind())() as worker:
        assert not lock_service.renew(worker, "crawler")
        assert lock_service.renew(worker, "crawler", owner=token)
        lock_service.release(worker, "crawler", owner=token)
    assert not lock_service.is_held(db, "crawler")


def test_manual_job_handoff_and_reset_do_not_release_new_owner(db, monkeypatch):
    from app.routers import crawler_router

    Session = sessionmaker(bind=db.get_bind())
    monkeypatch.setattr(crawler_router, "SessionLocal", Session)
    assert lock_service.try_acquire(db, "crawler")
    token = lock_service.lease_owner(db, "crawler")
    crawled = []
    scored = []

    with Session() as replacement:
        def crawl(worker, **kwargs):
            crawled.append(kwargs["board"])
            assert lock_service.lease_owner(worker, "crawler") == token
            lock_service.force_release(replacement, "crawler")
            assert lock_service.try_acquire(replacement, "crawler")

        monkeypatch.setattr(crawler_router, "_crawl_one_board", lambda db, **kw: crawl(db, **kw))
        monkeypatch.setattr(crawler_router, "classify_pending_sentiments", lambda db: scored.append(True))
        crawler_router._run_crawl_job("ptt", ["a", "b"], 1, None, token)
        assert crawled == ["a"]
        assert scored == []
        assert lock_service.is_held(replacement, "crawler")


def test_scheduled_job_stops_when_lease_is_lost(db, monkeypatch):
    from app.core import scheduler

    Session = sessionmaker(bind=db.get_bind())
    assert lock_service.try_acquire(db, "crawler")
    monkeypatch.setattr(scheduler, "get_setting", lambda *args: True)
    monkeypatch.setattr(scheduler, "get_active_crawl_targets", lambda db: [("ptt", "a")])
    monkeypatch.setattr(scheduler, "stop_requested", lambda: False)

    with Session() as replacement:
        class Crawler:
            def crawl_board(self, **kwargs):
                lock_service.force_release(replacement, "crawler")
                assert lock_service.try_acquire(replacement, "crawler")
                return []

        monkeypatch.setattr(scheduler, "get_crawler", lambda name: Crawler())
        with pytest.raises(lock_service.LockLost):
            scheduler._crawl_all_boards(db, 1)
        lock_service.release(db, "crawler")
        assert lock_service.is_held(replacement, "crawler")


def test_only_one_worker_can_take_over_expired_lease(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'locks.db').as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        past = taiwan_now() - timedelta(minutes=2)
        db.add(SystemLock(name="crawler", owner="old", acquired_at=past, expires_at=past))
        db.commit()
    barrier = Barrier(2)

    def acquire():
        with Session() as db:
            barrier.wait(timeout=10)
            return lock_service.try_acquire(db, "crawler")

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            assert sorted(workers.map(lambda _: acquire(), range(2))) == [False, True]
    finally:
        engine.dispose()


def test_fetch_timestamp_migration_preserves_existing_rows():
    migration = run_path(str(Path(__file__).parents[1] / "alembic/versions/f1a92b3c4d56_add_article_last_crawled_at.py"))
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE articles (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO articles (id) VALUES (1)"))
        with Operations.context(MigrationContext.configure(connection)):
            migration["upgrade"]()
            migration["upgrade"]()
            assert connection.execute(text("SELECT last_crawled_at FROM articles")).scalar() is None
            assert "last_crawled_at" in {c["name"] for c in inspect(connection).get_columns("articles")}
            migration["downgrade"]()
            assert connection.execute(text("SELECT id FROM articles")).scalar() == 1
    engine.dispose()
