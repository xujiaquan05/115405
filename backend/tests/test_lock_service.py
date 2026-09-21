# backend/tests/test_lock_service.py

"""跨行程互斥鎖。

原本的爬取旗標是 process 內的全域變數，多開一個 worker 就會同時跑兩批爬取。
改存資料庫後，這裡驗證互斥、逾時接手與釋放。
"""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.time_utils import taiwan_now
from app.models.database_models import SystemLock
from app.services import lock_service


@pytest.fixture
def sessions():
    """兩個獨立 session，模擬兩個 worker 共用同一個資料庫。"""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    first, second = Session(), Session()
    yield first, second
    first.close()
    second.close()


class TestMutualExclusion:
    def test_second_worker_cannot_acquire(self, sessions):
        worker_a, worker_b = sessions

        assert lock_service.try_acquire(worker_a, "crawler") is True
        assert lock_service.try_acquire(worker_b, "crawler") is False

    def test_release_lets_the_next_worker_in(self, sessions):
        worker_a, worker_b = sessions
        lock_service.try_acquire(worker_a, "crawler")

        lock_service.release(worker_a, "crawler")

        assert lock_service.try_acquire(worker_b, "crawler") is True

    def test_different_names_do_not_block_each_other(self, sessions):
        worker_a, worker_b = sessions

        assert lock_service.try_acquire(worker_a, "crawler") is True
        assert lock_service.try_acquire(worker_b, "something-else") is True


class TestExpiry:
    def test_expired_lock_is_taken_over(self, sessions):
        """持鎖的 worker 若被強制關閉就不會釋放；
        沒有到期時間的話這把鎖會永遠卡住，爬蟲再也發動不了。"""
        worker_a, worker_b = sessions
        lock_service.try_acquire(worker_a, "crawler")

        row = worker_a.query(SystemLock).one()
        row.expires_at = taiwan_now() - timedelta(minutes=1)
        worker_a.commit()

        assert lock_service.try_acquire(worker_b, "crawler") is True

    def test_unexpired_lock_is_not_taken_over(self, sessions):
        worker_a, worker_b = sessions
        lock_service.try_acquire(worker_a, "crawler", ttl_minutes=60)

        assert lock_service.try_acquire(worker_b, "crawler") is False


class TestHelpers:
    def test_is_held_reflects_state(self, sessions):
        worker_a, _ = sessions

        assert lock_service.is_held(worker_a, "crawler") is False

        lock_service.try_acquire(worker_a, "crawler")
        assert lock_service.is_held(worker_a, "crawler") is True

        lock_service.release(worker_a, "crawler")
        assert lock_service.is_held(worker_a, "crawler") is False

    def test_release_is_safe_when_not_held(self, sessions):
        worker_a, _ = sessions

        lock_service.release(worker_a, "crawler")  # 不應該拋錯


class TestScheduledJobRespectsTheLock:
    """排程與手動爬取必須共用同一把鎖。

    先前把鎖移進資料庫時只接上了 API 端點，排程仍直接開爬；
    凌晨排程啟動時若剛好有人從後台按下爬取，兩批會同時進行。
    """

    def test_daily_job_skips_when_a_crawl_is_running(self, sessions):
        from unittest.mock import patch

        from app.core import scheduler

        worker_a, _ = sessions
        lock_service.try_acquire(worker_a, lock_service.CRAWL_LOCK)

        with patch.object(scheduler, "SessionLocal", return_value=worker_a), \
             patch.object(scheduler, "get_setting", return_value=True), \
             patch.object(scheduler, "_crawl_all_boards") as crawl:
            result = scheduler.run_daily_job(pages=1, force=True)

        assert result == {"skipped": True, "reason": "crawl_in_progress"}
        crawl.assert_not_called()

    def test_lock_is_released_even_if_crawling_fails(self, sessions):
        """爬取途中出錯也要放開鎖，否則之後再也發不動。"""
        from unittest.mock import patch

        from app.core import scheduler

        worker_a, worker_b = sessions

        with patch.object(scheduler, "SessionLocal", return_value=worker_a), \
             patch.object(scheduler, "get_setting", return_value=True), \
             patch.object(scheduler, "_crawl_all_boards", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                scheduler.run_daily_job(pages=1, force=True)

        assert lock_service.try_acquire(worker_b, lock_service.CRAWL_LOCK) is True


class TestRenew:
    """爬取途中要能續約，否則鎖會在爬取還沒結束時到期。

    實測：一次完整爬取跑了超過 60 分鐘，而 TTL 正好也是 60 分鐘，
    鎖在爬取進行中就到期了。這時另一批爬取可以接手同一把鎖，
    兩批同時對來源站台發請求——正是這把鎖存在的目的。
    """

    def test_renew_extends_the_expiry(self, sessions):
        db, _other = sessions
        lock_service.try_acquire(db, "crawler", ttl_minutes=60)
        before = db.query(SystemLock).filter(SystemLock.name == "crawler").first().expires_at

        assert lock_service.renew(db, "crawler", ttl_minutes=120) is True

        after = db.query(SystemLock).filter(SystemLock.name == "crawler").first().expires_at
        assert after > before

    def test_renewing_a_lock_nobody_holds_fails(self, sessions):
        db, _other = sessions

        assert lock_service.renew(db, "crawler") is False

    def test_a_lock_taken_over_by_someone_else_cannot_be_renewed(self, sessions):
        db, _other = sessions
        lock_service.try_acquire(db, "crawler")
        lock = db.query(SystemLock).filter(SystemLock.name == "crawler").first()
        lock.owner = "pid-99999"  # 模擬鎖已被別的行程接手
        db.commit()

        # 搶回來的話就會變成兩批同時在跑，必須讓自己停下來。
        assert lock_service.renew(db, "crawler") is False
