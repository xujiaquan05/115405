import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from system_tests.support import BACKEND, PASSWORD, fake_generate_json, migrate
from system_tests.support import test_environment as server_env

pytestmark = pytest.mark.postgres


def test_legacy_init_sql_can_upgrade_without_losing_data(empty_postgres_url):
    engine = create_engine(empty_postgres_url)
    try:
        with engine.begin() as db:
            db.exec_driver_sql((BACKEND.parent / "database/init.sql").read_text(encoding="utf-8"))
            db.execute(text("INSERT INTO articles(unique_id,platform_id,title) "
                            "SELECT 'legacy-row',id,'preserve original data' FROM platforms WHERE name='ptt'"))
        migrate(empty_postgres_url)
        with engine.connect() as db:
            assert db.execute(text("SELECT title FROM articles WHERE unique_id='legacy-row'")).scalar_one() == "preserve original data"
            assert db.execute(text("SELECT count(*) FROM boards WHERE is_active=1")).scalar_one() > 0
    finally:
        engine.dispose()


def test_legacy_init_sql_upgrade_matches_the_models_on_boards(empty_postgres_url):
    # init.sql gave boards.platform_id ON DELETE CASCADE and the baseline added
    # is_active with a plain ADD COLUMN, so a database born before Alembic ends up
    # looser than the models. A database built from the baseline alone never shows
    # this, which is why the drift survived until a7d31c6f0e92.
    engine = create_engine(empty_postgres_url)
    try:
        with engine.begin() as db:
            db.exec_driver_sql((BACKEND.parent / "database/init.sql").read_text(encoding="utf-8"))
        with engine.connect() as db:
            assert db.execute(text(
                "SELECT confdeltype FROM pg_constraint WHERE conname='boards_platform_id_fkey'"
            )).scalar_one() == "c", "init.sql should start out with CASCADE"

        migrate(empty_postgres_url)

        with engine.connect() as db:
            assert db.execute(text(
                "SELECT confdeltype FROM pg_constraint WHERE conname='boards_platform_id_fkey'"
            )).scalar_one() == "a", "upgrade should leave NO ACTION, as the model declares"
            assert db.execute(text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='boards' AND column_name='is_active'"
            )).scalar_one() == "NO"

        migrate(empty_postgres_url, "f1a92b3c4d56", "downgrade")

        with engine.connect() as db:
            assert db.execute(text(
                "SELECT confdeltype FROM pg_constraint WHERE conname='boards_platform_id_fkey'"
            )).scalar_one() == "c", "downgrade should put CASCADE back"
            assert db.execute(text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='boards' AND column_name='is_active'"
            )).scalar_one() == "YES"
    finally:
        engine.dispose()


def test_empty_database_migrates_to_head_and_bootstraps_twice(postgres_url):
    # Real production ordering: Alembic first, startup second. No create_all in fixtures.
    result = subprocess.run(
        [sys.executable, "-c", "from app.core.startup import initialize_database; initialize_database(); initialize_database()"],
        cwd=BACKEND, env=server_env(postgres_url), capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_migrated_schema_matches_model_columns_and_foreign_keys(pg_engine):
    from app.core.database import Base
    from app.models import database_models  # noqa: F401

    inspector = inspect(pg_engine)
    for table in Base.metadata.sorted_tables:
        assert {c.name for c in table.columns} == {c["name"] for c in inspector.get_columns(table.name)}
        expected = {(tuple(c.name for c in fk.columns), fk.referred_table.name, fk.ondelete)
                    for fk in table.foreign_key_constraints}
        actual = {(tuple(fk["constrained_columns"]), fk["referred_table"], fk["options"].get("ondelete"))
                  for fk in inspector.get_foreign_keys(table.name)}
        assert expected <= actual, table.name


def test_last_crawl_migration_preserves_existing_data(postgres_url, pg_engine):
    migrate(postgres_url, "e4f70c2a9d18", "downgrade")
    with pg_engine.begin() as db:
        platform = db.execute(text("INSERT INTO platforms(name) VALUES ('legacy') RETURNING id")).scalar_one()
        db.execute(text("INSERT INTO articles(unique_id,platform_id,title) VALUES ('legacy',:pid,'keep me')"), {"pid": platform})
    migrate(postgres_url)
    migrate(postgres_url)
    with pg_engine.connect() as db:
        assert db.execute(text("SELECT title,last_crawled_at FROM articles WHERE unique_id='legacy'")).one() == ("keep me", None)


def test_foreign_keys_reject_orphans_and_cascade_on_delete(seeded_engine):
    with seeded_engine.connect() as db:
        with pytest.raises(IntegrityError):
            db.execute(text("INSERT INTO watch_keywords(user_id,keyword,days,enabled) VALUES (-1,'orphan',7,1)"))
        db.rollback()
    with seeded_engine.begin() as db:
        uid = db.execute(text("SELECT id FROM users WHERE username='alice'")).scalar_one()
        db.execute(text("INSERT INTO watch_keywords(user_id,keyword,days,enabled) VALUES (:id,'owned',7,1)"), {"id": uid})
        db.execute(text("INSERT INTO audit_logs(actor_id,actor_username,action) VALUES (:id,'alice','test')"), {"id": uid})
        db.execute(text("DELETE FROM users WHERE id=:id"), {"id": uid})
        assert db.execute(text("SELECT count(*) FROM watch_keywords WHERE user_id=:id"), {"id": uid}).scalar_one() == 0
        assert db.execute(text("SELECT actor_id FROM audit_logs WHERE actor_username='alice'")).scalar_one() is None


@pytest.mark.parametrize("expired", [False, True])
def test_concurrent_postgres_lock_acquisition_has_one_winner(pg_engine, expired):
    from app.core.time_utils import taiwan_now
    from app.models.database_models import SystemLock
    from app.services import lock_service

    if expired:
        with Session(pg_engine) as db:
            past = taiwan_now() - timedelta(minutes=2)
            db.add(SystemLock(name="crawler", owner="old", acquired_at=past, expires_at=past))
            db.commit()
    barrier = Barrier(4)

    def acquire(_):
        with Session(pg_engine) as db:
            barrier.wait(timeout=10)
            return lock_service.try_acquire(db, "crawler")

    with ThreadPoolExecutor(max_workers=4) as workers:
        assert list(workers.map(acquire, range(4))).count(True) == 1


@pytest.fixture
def client(seeded_engine, monkeypatch):
    from app.core.database import get_db
    from app.main import app
    from app.services import llm_analysis_service, rag_service
    from app.services.cache_service import CACHE_STORE

    def get_test_db():
        with Session(seeded_engine) as db:
            yield db

    CACHE_STORE.clear()
    monkeypatch.setattr(llm_analysis_service, "generate_json_response", fake_generate_json)
    monkeypatch.setattr(rag_service, "generate_json_response", fake_generate_json)
    app.dependency_overrides[get_db] = get_test_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        CACHE_STORE.clear()


def login(client, username):
    result = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert result.status_code == 200, result.text
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def test_api_search_json_history_tenancy_and_export(client):
    from io import BytesIO
    from zipfile import ZipFile

    alice = login(client, "alice")
    response = client.get("/api/dashboard/full", params={"keyword": "玻尿酸", "boards": "ptt:facelift"})
    assert response.status_code == 200
    assert response.json()["data"]["overview"]["total_articles"] == 1
    result = client.get("/api/analysis/keyword", params={"keyword": "玻尿酸"}, headers=alice)
    assert result.status_code == 200, result.text
    records = client.get("/api/analysis/history", headers=alice).json()["data"]["records"]
    assert len(records) == 1
    bob = login(client, "bob")
    assert client.get("/api/analysis/history", headers=bob).json()["data"]["records"] == []
    assert client.delete(f"/api/analysis/history/{records[0]['id']}", headers=bob).status_code == 404
    export = client.get("/api/export/articles.xlsx", params={"keyword": "玻尿酸", "boards": "ptt:facelift"}, headers=alice)
    assert export.status_code == 200
    with ZipFile(BytesIO(export.content)) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode()
        assert "E2E PTT" in sheet
        assert "E2E Dcard" not in sheet


def test_qa_quota_and_guest_permissions_use_real_postgres(client, seeded_engine):
    alice = login(client, "alice")
    with seeded_engine.begin() as db:
        db.execute(text("UPDATE plans SET monthly_qa_quota=1 WHERE code='pro'"))
    payload = {"question": "目前的重點是什麼？", "dashboard_context": {"keyword": "玻尿酸", "days": 30}}
    assert client.post("/api/qa/ask", json=payload, headers=alice).status_code == 200
    assert client.post("/api/qa/ask", json=payload, headers=alice).status_code == 403
    with seeded_engine.connect() as db:
        assert db.execute(text("SELECT qa_count FROM usage_counters")).scalar_one() == 1
    client.post("/api/auth/logout")
    assert client.post("/api/qa/ask", json=payload).status_code == 401
    assert client.get("/api/export/articles.xlsx").status_code == 401
