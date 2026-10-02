"""Create only uniquely named disposable databases on an explicit test server."""

import os
import re
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
ARTIFACTS = BACKEND / ".test-artifacts"
PASSWORD = "System-test-pass-5948!"


def test_environment(url):
    return {
        **os.environ,
        "DATABASE_URL": url,
        "PYTHON_DOTENV_DISABLED": "1",
        "GOOGLE_API_KEY": "",
        "JWT_SECRET": "isolated-system-tests-only-5948-not-for-production",
        "PBKDF2_ITERATIONS": "1000",
        "APP_ENV": "development",
        "ADMIN_PASSWORD": PASSWORD,
        "AUTO_CRAWL_ENABLED": "false",
        "STARTUP_CATCHUP_ENABLED": "false",
        "DCARD_CRAWL_ENABLED": "false",
        "MOBILE01_CRAWL_ENABLED": "false",
        "THREADS_CRAWL_ENABLED": "false",
    }


@contextmanager
def disposable_database(admin_url):
    url = make_url(admin_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("TEST_POSTGRES_URL must point to a PostgreSQL test server")
    name = "mebod_test_" + uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    created = False
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        yield url.set(database=name).render_as_string(hide_password=False)
    finally:
        if created:
            # Never derive a DROP target from user configuration or DATABASE_URL.
            assert re.fullmatch(r"mebod_test_[0-9a-f]{32}", name)
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def migrate(url, revision="head", action="upgrade"):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", action, revision],
        cwd=BACKEND, env=test_environment(url), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60,
    )
    if result.returncode:
        raise AssertionError(f"Migration {action} {revision} failed:\n{result.stdout}\n{result.stderr}")


def seed_data(engine):
    from sqlalchemy.orm import Session

    from app.core.startup import _seed_plans
    from app.core.time_utils import taiwan_now
    from app.models.database_models import User
    from app.services.article_service import create_article, save_comments
    from app.services.auth_service import hash_password

    with Session(engine) as db:
        _seed_plans(db)
        db.commit()
        for name, plan in (("alice", "pro"), ("bob", "pro"), ("freeuser", "free")):
            db.add(User(username=name, password_hash=hash_password(PASSWORD),
                        display_name=name, role="user", is_active=1, plan_code=plan))
        db.commit()
        for platform, title in (("ptt", "玻尿酸 E2E PTT 心得"), ("dcard", "玻尿酸 E2E Dcard 心得")):
            article, _ = create_article(
                db, f"e2e-{platform}", platform, "facelift", "tester", title,
                "玻尿酸療程後保濕效果很好，這是系統測試的固定樣本。",
                f"https://example.test/{platform}", push_count=20, published_at=taiwan_now(),
            )
            article.sentiment = "positive"
            db.commit()
            save_comments(db, article, ["效果很好", "術後有點腫脹"])


def fake_generate_json(prompt):
    """Replace only the external LLM boundary; API, retrieval and storage stay real."""
    import json

    return json.dumps({
        "summary": "E2E 固定洞察：關注術後保濕與腫脹。",
        "answer": "E2E 固定回答：樣本提到保濕效果，應持續追蹤術後腫脹。",
        "key_points": ["追蹤術後反應"], "marketing_action": "說明術後照護流程",
        "confidence": "high", "hot_topics": [], "consumer_pain_points": [],
        "marketing_suggestions": [],
    }, ensure_ascii=False)
