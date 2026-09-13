"""讓進行中的爬取能夠被「請求中止」的共用旗標。

為什麼需要這個？
爬取跑在背景執行緒（APScheduler 的 ThreadPoolExecutor）裡，而
concurrent.futures 會在直譯器結束時 join 這些執行緒。
只要爬蟲還卡在 time.sleep 或等網頁，整個行程就無法結束——
開發時用 --reload 存檔重啟，舊的 server 會停止服務卻又死不掉，
連接埠被它佔著，前端送出的請求就一直卡住沒有回應
（症狀正是「登入失敗，請確認網路或 backend 狀態」）。

作法：關閉時設下旗標，爬蟲每次禮貌性延遲都會檢查，
收到就丟出 CrawlAborted 讓流程盡快收手，行程才能正常結束。
"""

import random
import threading

_stop_event = threading.Event()


class CrawlAborted(Exception):
    """爬取因為系統要關閉而提前中止。

    不是錯誤，所以呼叫端應該分開處理：
    記一筆 info log 就好，不要當成該看板爬取失敗。
    """


def request_stop() -> None:
    """通知所有進行中的爬取盡快停止。"""
    _stop_event.set()


def clear_stop() -> None:
    """清除停止旗標（行程重新啟動或測試之間使用）。"""
    _stop_event.clear()


def stop_requested() -> bool:
    """目前是否已要求停止。"""
    return _stop_event.is_set()


def sleep_or_abort(seconds: float) -> None:
    """可被中斷的延遲。

    用 Event.wait 取代 time.sleep：收到停止要求時會立刻醒來，
    不必等完整個延遲時間。
    """
    if _stop_event.wait(seconds):
        raise CrawlAborted("系統正在關閉，爬取中止")


def random_sleep_or_abort(min_seconds: float, max_seconds: float) -> None:
    """隨機長度的可中斷延遲（爬蟲禮貌性延遲用）。"""
    sleep_or_abort(random.uniform(min_seconds, max_seconds))
