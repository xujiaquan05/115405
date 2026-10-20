# backend/tests/test_startup_catchup.py

"""啟動時補跑每日任務。

背景：排程只在後端執行中才會觸發。本機使用時半夜三點電腦通常是關的，
而 APScheduler 預設不補跑錯過的排程——查資料庫可以看到排程設好了卻從未執行，
所有爬取都發生在使用者實際操作的時段。

補跑讓「每天開一次後端」就足以收到當天資料。
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import scheduler
from app.core.database import Base
from app.core.time_utils import taiwan_now
from app.services.settings_service import set_internal_value


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


class TestHasRunToday:
    def test_false_when_never_run(self, db):
        assert scheduler.has_run_today(db) is False

    def test_true_after_todays_run_is_recorded(self, db):
        set_internal_value(db, scheduler.LAST_RUN_KEY, taiwan_now().strftime("%Y-%m-%d"))

        assert scheduler.has_run_today(db) is True

    def test_false_when_the_record_is_from_yesterday(self, db):
        yesterday = (taiwan_now() - timedelta(days=1)).strftime("%Y-%m-%d")
        set_internal_value(db, scheduler.LAST_RUN_KEY, yesterday)

        assert scheduler.has_run_today(db) is False


class TestScheduleStartupCatchup:
    """_schedule_startup_catchup 只負責決定「要不要排補跑」。"""

    def _run(self, db, settings, scheduler_stub):
        def fake_get_setting(_db, key):
            return settings[key]

        with patch.object(scheduler, "SessionLocal", return_value=db), \
             patch.object(scheduler, "get_setting", side_effect=fake_get_setting), \
             patch.object(scheduler, "_scheduler", scheduler_stub):
            scheduler._schedule_startup_catchup()

    def test_schedules_when_not_run_today(self, db):
        stub = _SchedulerStub()

        self._run(db, {"auto_crawl_enabled": True, "startup_catchup_enabled": True}, stub)

        assert len(stub.jobs) == 1
        assert stub.jobs[0]["id"] == scheduler.CATCHUP_JOB_ID

    def test_does_not_schedule_when_already_run_today(self, db):
        set_internal_value(db, scheduler.LAST_RUN_KEY, taiwan_now().strftime("%Y-%m-%d"))
        stub = _SchedulerStub()

        self._run(db, {"auto_crawl_enabled": True, "startup_catchup_enabled": True}, stub)

        assert stub.jobs == []

    def test_respects_the_catchup_switch(self, db):
        stub = _SchedulerStub()

        self._run(db, {"auto_crawl_enabled": True, "startup_catchup_enabled": False}, stub)

        assert stub.jobs == []

    def test_does_not_run_when_auto_crawl_is_off(self, db):
        """整個自動爬取關掉時，補跑也不該偷偷開始。"""
        stub = _SchedulerStub()

        self._run(db, {"auto_crawl_enabled": False, "startup_catchup_enabled": True}, stub)

        assert stub.jobs == []


class _SchedulerStub:
    def __init__(self):
        self.jobs = []

    def add_job(self, func, **kwargs):
        self.jobs.append({"func": func, **kwargs})


class TestRetryMissedDailyJob:
    """後端一直開著、但當天任務被錯過或中途放棄時，每小時檢查並補跑。

    115/10/19 實際情況：補跑在 01:01 開始，01:23 電腦睡眠；21:31 醒來時租約已過期，
    該批結果被放棄，而 03:00 的排程也因睡眠被略過，整天沒有收錄。
    """

    SETTINGS = {"auto_crawl_enabled": True, "startup_catchup_enabled": True, "auto_crawl_hour": 3}

    def _should(self, db, hour, settings=None):
        values = {**self.SETTINGS, **(settings or {})}
        now = taiwan_now().replace(hour=hour, minute=30)
        with patch.object(scheduler, "get_setting", side_effect=lambda _db, key: values[key]):
            return scheduler.should_retry_daily_job(db, now=now)

    def test_retries_after_the_scheduled_hour_when_not_run_today(self, db):
        assert self._should(db, hour=21) is True

    def test_waits_until_the_scheduled_hour(self, db):
        assert self._should(db, hour=1) is False

    def test_skips_when_already_run_today(self, db):
        set_internal_value(db, scheduler.LAST_RUN_KEY, taiwan_now().strftime("%Y-%m-%d"))

        assert self._should(db, hour=21) is False

    def test_respects_the_switches(self, db):
        assert self._should(db, hour=21, settings={"auto_crawl_enabled": False}) is False
        assert self._should(db, hour=21, settings={"startup_catchup_enabled": False}) is False

    def test_runs_the_daily_job_only_when_needed(self, db):
        calls = []
        with patch.object(scheduler, "SessionLocal", return_value=db),              patch.object(scheduler, "should_retry_daily_job", return_value=True),              patch.object(scheduler, "run_daily_job", side_effect=lambda: calls.append(1) or {"ok": True}):
            assert scheduler.retry_missed_daily_job() == {"ok": True}

        with patch.object(scheduler, "SessionLocal", return_value=db),              patch.object(scheduler, "should_retry_daily_job", return_value=False),              patch.object(scheduler, "run_daily_job", side_effect=lambda: calls.append(1)):
            assert scheduler.retry_missed_daily_job() is None

        assert calls == [1]


def test_daily_cron_runs_late_after_sleep_instead_of_being_skipped():
    """排程時間電腦在睡眠時，醒來要補跑，而不是因為超過 1 秒寬限就略過。"""
    jobs = {}

    class _Recorder:
        def __init__(self, **_kwargs):
            pass

        def add_job(self, func, **kwargs):
            jobs[kwargs["id"]] = kwargs

        def start(self):
            pass

    with patch.object(scheduler, "BackgroundScheduler", _Recorder),          patch.object(scheduler, "_scheduler", None),          patch.object(scheduler, "_read_schedule_hour", return_value=3),          patch.object(scheduler, "_schedule_startup_catchup"),          patch.object(scheduler, "clear_stop"):
        scheduler.start_scheduler()
        scheduler._scheduler = None

    assert jobs[scheduler.JOB_ID]["misfire_grace_time"] is None
    assert jobs[scheduler.JOB_ID]["coalesce"] is True
    assert jobs[scheduler.RETRY_JOB_ID]["minutes"] == scheduler.RETRY_INTERVAL_MINUTES
