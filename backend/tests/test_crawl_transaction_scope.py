# backend/tests/test_crawl_transaction_scope.py

"""爬取期間不應該佔著資料庫交易。

背景（實際量測到的）：
排程爬取時查 pg_stat_activity，看到一條連線停在
`idle in transaction` 長達 18 分鐘——SQLAlchemy 在第一次查詢就開啟交易，
而 get_or_create_platform / get_or_create_board 在「看板早就存在」的
日常情況下只做 SELECT、不會 commit，於是那個交易就一路開著等爬蟲跑完。

代價是一條連線被佔住不放，而且 autovacuum 無法回收這段期間的舊資料列。
爬取本身完全不碰資料庫，所以出發前先結束交易，一個看板一個交易。
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import scheduler, shutdown
from app.core.database import Base
from app.services import lock_service
from app.services.article_service import get_or_create_board, get_or_create_platform

BOARDS = [("ptt", "a"), ("ptt", "b")]


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    # 先把平台與看板建好，重現「日常情況」：
    # get_or_create_* 只會 SELECT，不會順手 commit 幫我們結束交易。
    platform = get_or_create_platform(session, "ptt")
    for _platform_name, board_name in BOARDS:
        get_or_create_board(session, platform.id, board_name)
    session.commit()

    # 爬取一定是在持有爬取鎖的情況下進行的（run_daily_job 先取鎖才呼叫），
    # 而 _crawl_all_boards 每個看板都會續約。不先取鎖的話會一開始就中止。
    lock_service.try_acquire(session, lock_service.CRAWL_LOCK)

    yield session
    session.close()


@pytest.fixture(autouse=True)
def reset_stop_flag():
    shutdown.clear_stop()
    yield
    shutdown.clear_stop()


def _patch_crawler(monkeypatch, crawl_board):
    monkeypatch.setattr(scheduler, "get_active_crawl_targets", lambda _db: BOARDS)
    monkeypatch.setattr(scheduler, "get_setting", lambda _db, _key: True)
    monkeypatch.setattr(
        scheduler, "get_crawler", lambda _name: SimpleNamespace(crawl_board=crawl_board)
    )


class TestTransactionScope:
    def test_no_transaction_is_open_while_a_board_is_being_crawled(self, db, monkeypatch):
        open_during_crawl = []

        def crawl_board(board, pages):
            open_during_crawl.append(db.in_transaction())
            return []

        _patch_crawler(monkeypatch, crawl_board)
        scheduler._crawl_all_boards(db, pages=1)

        # 這是重點：兩個看板都要在「沒有交易」的狀態下出發。
        assert open_during_crawl == [False, False]

    def test_the_session_still_works_after_a_board_fails(self, db, monkeypatch):
        crawled = []

        def crawl_board(board, pages):
            crawled.append(board)
            if board == "a":
                raise RuntimeError("boom")
            return []

        _patch_crawler(monkeypatch, crawl_board)
        scheduler._crawl_all_boards(db, pages=1)

        # 失敗的看板若沒有 rollback，下一個看板的查詢會直接拋 PendingRollbackError。
        assert crawled == ["a", "b"]
        assert get_or_create_platform(db, "ptt") is not None

    def test_the_session_is_clean_after_an_abort(self, db, monkeypatch):
        def crawl_board(board, pages):
            shutdown.request_stop()
            raise shutdown.CrawlAborted("系統正在關閉，爬取中止")

        _patch_crawler(monkeypatch, crawl_board)
        scheduler._crawl_all_boards(db, pages=1)

        assert db.in_transaction() is False
