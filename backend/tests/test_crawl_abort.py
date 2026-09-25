# backend/tests/test_crawl_abort.py

"""關閉後端時，進行中的爬取要能被中止。

背景（實際發生過的故障）：
爬取跑在 APScheduler 的 ThreadPoolExecutor 執行緒裡，而 concurrent.futures
會在直譯器結束時 join 這些執行緒。爬蟲那時卡在禮貌性延遲與等待網頁，
於是 --reload 存檔重啟後，舊的 server 行程停止服務卻無法結束，
還佔著 8000 埠；前端送出的請求全部沒有回應，畫面顯示
「登入失敗，請確認網路或 backend 狀態」。

修正：關閉時設下停止旗標，爬蟲的每次延遲都會檢查並丟出 CrawlAborted。
"""

import threading
import time
from types import SimpleNamespace

import pytest

from app.core import scheduler, shutdown
from app.core.shutdown import CrawlAborted
from app.crawlers.browser_base import BrowserCrawler
from app.services import lock_service


@pytest.fixture(autouse=True)
def reset_stop_flag():
    """每個測試都從「沒有要求停止」開始，並確保不影響其他測試。"""
    shutdown.clear_stop()
    yield
    shutdown.clear_stop()


class TestSleepOrAbort:
    def test_sleeps_normally_when_no_stop_requested(self):
        started = time.monotonic()
        shutdown.sleep_or_abort(0.05)
        elapsed = time.monotonic() - started

        # 容差：Windows 的計時器解析度約 15.6ms，Event.wait 可能略早返回，
        # 拿 0.05 當嚴格下限會偶發失敗（實測在完整測試套件中出現過）。
        # 這裡要驗的是「沒有被要求停止時不會提早中斷」，不是精準計時。
        assert elapsed >= 0.03

    def test_raises_immediately_when_stop_already_requested(self):
        shutdown.request_stop()

        started = time.monotonic()
        with pytest.raises(CrawlAborted):
            shutdown.sleep_or_abort(30)

        # 重點：不必等完 30 秒。行程能不能結束就取決於這件事。
        assert time.monotonic() - started < 1

    def test_wakes_up_when_stop_is_requested_during_the_sleep(self):
        threading.Timer(0.05, shutdown.request_stop).start()

        started = time.monotonic()
        with pytest.raises(CrawlAborted):
            shutdown.sleep_or_abort(30)

        assert time.monotonic() - started < 1


class TestCrawlerSleep:
    """爬蟲的禮貌性延遲要走可中斷的版本。"""

    def test_browser_crawler_sleep_aborts(self):
        crawler = BrowserCrawler(min_delay=30, max_delay=30)
        shutdown.request_stop()

        started = time.monotonic()
        with pytest.raises(CrawlAborted):
            crawler._sleep()

        assert time.monotonic() - started < 1


class TestShutdownScheduler:
    def test_shutdown_requests_stop_even_without_a_scheduler(self):
        scheduler.shutdown_scheduler()

        assert shutdown.stop_requested() is True


class FakeSession:
    """只需要 commit / rollback 的假 session（這些測試不寫入資料）。"""

    def __init__(self):
        self.rolled_back = 0

    def commit(self):
        pass

    def rollback(self):
        self.rolled_back += 1


class TestCrawlAllBoardsStopsEarly:
    """_crawl_all_boards 收到停止要求時不再開下一個看板。"""

    def _patch(self, monkeypatch, targets, crawl_board):
        # 這些測試用的是假 session，沒有真的鎖可以續約。
        # 續約本身由 test_lock_service.py 驗證，這裡只關心中止邏輯。
        monkeypatch.setattr(lock_service, "renew", lambda _db, _name: True)
        monkeypatch.setattr(scheduler, "get_active_crawl_targets", lambda _db: targets)
        monkeypatch.setattr(scheduler, "get_setting", lambda _db, _key: True)
        monkeypatch.setattr(scheduler, "get_or_create_platform", lambda _db, _name: SimpleNamespace(id=1))
        monkeypatch.setattr(scheduler, "get_or_create_board", lambda _db, _pid, _name: SimpleNamespace(id=1))

        fake_crawler = SimpleNamespace(crawl_board=crawl_board)
        monkeypatch.setattr(scheduler, "get_crawler", lambda _name: fake_crawler)

    def test_does_not_start_the_next_board_after_stop(self, monkeypatch):
        crawled: list[str] = []

        def crawl_board(board, pages):
            crawled.append(board)
            shutdown.request_stop()  # 模擬第一個看板跑到一半時後端開始關閉
            return []

        self._patch(monkeypatch, [("ptt", "a"), ("ptt", "b"), ("ptt", "c")], crawl_board)

        assert scheduler._crawl_all_boards(db=FakeSession(), pages=1) == 0
        assert crawled == ["a"]

    def test_crawl_aborted_is_not_treated_as_a_board_failure(self, monkeypatch):
        crawled: list[str] = []

        def crawl_board(board, pages):
            crawled.append(board)
            raise CrawlAborted("系統正在關閉，爬取中止")

        self._patch(monkeypatch, [("ptt", "a"), ("ptt", "b")], crawl_board)

        # 中止要停下整輪，而不是跳過這個看板再去爬下一個。
        assert scheduler._crawl_all_boards(db=FakeSession(), pages=1) == 0
        assert crawled == ["a"]

    def test_a_failing_board_still_does_not_stop_the_others(self, monkeypatch):
        crawled: list[str] = []

        def crawl_board(board, pages):
            crawled.append(board)
            if board == "a":
                raise RuntimeError("boom")
            return []

        self._patch(monkeypatch, [("ptt", "a"), ("ptt", "b")], crawl_board)

        assert scheduler._crawl_all_boards(db=FakeSession(), pages=1) == 0
        assert crawled == ["a", "b"]
