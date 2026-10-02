import os

import pytest
from sqlalchemy import create_engine

from system_tests.support import disposable_database, migrate, seed_data


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, "rep_" + report.when, report)


@pytest.fixture
def empty_postgres_url():
    admin_url = os.environ.get("TEST_POSTGRES_URL")
    if not admin_url:
        pytest.fail("Set TEST_POSTGRES_URL to a dedicated PostgreSQL server with CREATEDB permission; no .env fallback")
    with disposable_database(admin_url) as url:
        yield url


@pytest.fixture
def postgres_url(empty_postgres_url):
    migrate(empty_postgres_url)
    return empty_postgres_url


@pytest.fixture
def pg_engine(postgres_url):
    engine = create_engine(postgres_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def seeded_engine(pg_engine):
    seed_data(pg_engine)
    return pg_engine
