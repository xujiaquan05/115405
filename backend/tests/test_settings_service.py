# backend/tests/test_settings_service.py

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.services import settings_service


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


class TestSettings:
    def test_defaults_when_empty(self, db):
        assert settings_service.get_setting(db, "alert_warning_negative") == 25.0
        assert settings_service.get_setting(db, "alert_critical_negative") == 40.0
        assert settings_service.get_setting(db, "alert_min_articles") == 5
        assert settings_service.get_setting(db, "auto_crawl_enabled") is True
        assert settings_service.get_setting(db, "auto_crawl_hour") == 3

    def test_update_and_read_back(self, db):
        settings_service.update_settings(db, {
            "alert_warning_negative": 30,
            "alert_critical_negative": 55,
            "auto_crawl_enabled": False,
            "auto_crawl_hour": 6,
        })

        assert settings_service.get_setting(db, "alert_warning_negative") == 30.0
        assert settings_service.get_setting(db, "alert_critical_negative") == 55.0
        assert settings_service.get_setting(db, "auto_crawl_enabled") is False
        assert settings_service.get_setting(db, "auto_crawl_hour") == 6

    def test_get_all(self, db):
        alls = settings_service.get_all_settings(db)
        assert set(alls.keys()) == set(settings_service.SETTING_DEFS.keys())

    def test_unknown_key_ignored(self, db):
        settings_service.update_settings(db, {"evil_key": "x", "alert_min_articles": 8})
        alls = settings_service.get_all_settings(db)
        assert "evil_key" not in alls
        assert alls["alert_min_articles"] == 8

    def test_invalid_value_skipped(self, db):
        # 非數字丟給 float 欄位 → 跳過，保留預設。
        settings_service.update_settings(db, {"alert_warning_negative": "abc"})
        assert settings_service.get_setting(db, "alert_warning_negative") == 25.0
