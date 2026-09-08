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
