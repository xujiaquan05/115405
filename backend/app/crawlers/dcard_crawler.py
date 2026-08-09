"""Dcard 爬蟲（透過 Playwright 攔截 API 回應）。

為什麼不像 PTT 那樣直接用 requests？
Dcard（2026）位於 Cloudflare 之後，且鎖死了公開 API：
- headless 瀏覽器會被立即擋下（HTTP 429）。
- 用 requests / fetch 手動打 API 會被 WAF 擋（403）。
- 唯一穩定的作法：開「真的」瀏覽器（headed），讓 Dcard 前端自己去打 API，
  我們在旁邊「攔截（intercept）」它的 JSON 回應，再往下捲動觸發無限捲軸載入更多。

資料路徑（實測）：
- 文章列表：/f/{alias} 頁 → 回應 'globalPaging/page'
             → widgets[].forumList.items[].post

為了讓下游流程（relevance_filter → create_article → Gemini 情緒評分）
不必修改，本爬蟲輸出的欄位刻意對齊 PTTCrawler：
    platform_name / board_name / author_username / title / content /
    url / push_count / published_at / unique_id

注意：
- Dcard 文章多為匿名，沒有帳號名稱；此處以「學校 or 匿名」當作者。
- push_count 對應 Dcard 的 likeCount（Dcard 沒有負推，皆為非負值）。
- 內文採用列表回傳的 excerpt（摘要），避免逐篇進入內頁（每篇約 30 秒）拖慢整體。
"""

import hashlib
import random
import time
from datetime import datetime
from typing import Callable, Optional


class DcardCrawler:
    """負責爬取 Dcard 論壇（看板）的文章。"""

    BASE_URL = "https://www.dcard.tw"

    # 一次無限捲軸大約載入 30 篇，pages 因此換算成「目標文章數」。
    POSTS_PER_PAGE = 30

    # Dcard 會偵測自動化，以真實的 User-Agent 降低被擋機率。
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    )

    # 減少 Cloudflare 常檢查的自動化痕跡。
    STEALTH_JS = (
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        "Object.defineProperty(navigator, 'languages', {get: () => ['zh-TW','zh','en']});"
        "window.chrome = { runtime: {} };"
    )

    def __init__(self, headless: bool = False, min_delay: float = 1.5, max_delay: float = 3.5):
        # headless 預設 False：Dcard 會擋 headless。除非測試/特殊情況才開 True。
        self.headless = headless
        self.min_delay = min_delay
        self.max_delay = max_delay

    # ── 純函式工具（不需瀏覽器，便於單元測試） ──────────────────

    def _generate_unique_id(self, platform: str, board: str, url: str) -> str:
        """產生文章唯一 ID，讓重複爬取時能判斷是否已存在（與 PTT 一致）。"""
        raw_text = f"{platform}:{board}:{url}"
        return hashlib.md5(raw_text.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_dt(value) -> Optional[datetime]:
        """解析 Dcard 的 ISO 時間字串（例如 2026-01-05T12:00:00.000Z）。"""
        if not value or not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        # 統一存成不帶時區的 datetime，和其他平台的欄位一致。
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed

    @staticmethod
    def _extract_posts(bodies: list) -> list[dict]:
        """從多個 globalPaging/page 回應中彙整所有 post 物件（並依 id 去重）。"""
        posts: dict[int, dict] = {}

        for body in bodies:
            if not isinstance(body, dict):
                continue

            for widget in body.get("widgets", []):
                forum_list = widget.get("forumList") if isinstance(widget, dict) else None
                if not forum_list:
                    continue

                for item in forum_list.get("items", []):
                    post = item.get("post") if isinstance(item, dict) else None
                    if isinstance(post, dict) and "id" in post:
                        posts[post["id"]] = post  # 相同 id 覆蓋，自動去重

        return list(posts.values())

    def _to_article(self, post: dict, board: str) -> dict:
        """把 Dcard 的 post 物件轉成本專案統一的文章 dict。"""
        post_id = post.get("id")
        url = f"{self.BASE_URL}/f/{board}/p/{post_id}"
        author = post.get("anonymousSchool") or post.get("school") or "Dcard 匿名"

        return {
            "platform_name": "dcard",
            "board_name": board,
            "author_username": author,
            "title": post.get("title") or "",
            "content": post.get("excerpt") or "",
            "url": url,
            "push_count": post.get("likeCount") or 0,
            "published_at": self._parse_dt(post.get("createdAt")),
            "unique_id": self._generate_unique_id("dcard", board, url),
        }

    def _sleep(self) -> None:
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    # ── 瀏覽器驅動的爬取 ────────────────────────────────────────

    def crawl_board(
        self,
        board: str = "makeup",
        pages: int = 1,
        start_page: int | None = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[dict]:
        """爬取一個 Dcard 看板的文章列表。

        參數對齊 PTTCrawler：
        - pages：以「頁」為單位，內部換算為 pages × POSTS_PER_PAGE 篇目標文章數。
        - start_page：Dcard 為無限捲軸，沒有頁碼概念，保留參數但忽略。
        - progress_callback：回報進度（給 WebSocket 用）。

        回傳與 PTTCrawler 相同格式的文章 dict 清單。
        """
        max_posts = max(1, pages) * self.POSTS_PER_PAGE

        # 延遲載入 Playwright：未安裝時不影響整個後端與測試的匯入。
        try:
            from playwright.sync_api import TimeoutError as PWTimeout
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "Dcard 爬蟲需要 Playwright，請先安裝："
                "pip install playwright 並執行 playwright install chromium"
            ) from error

        bodies: list = []

        def on_response(resp):
            if "globalPaging/page" in resp.url:
                try:
                    bodies.append(resp.json())
                except Exception:
                    pass  # 略過非 JSON 回應

        playwright = sync_playwright().start()
        browser = None

        try:
            browser = playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=self.USER_AGENT,
                locale="zh-TW",
                viewport={"width": 1280, "height": 900},
            )
            context.add_init_script(self.STEALTH_JS)
            page = context.new_page()

            # 關閉 HTTP 快取：否則重訪時回應來自快取，Playwright 取不到 body。
            cdp = context.new_cdp_session(page)
            cdp.send("Network.enable")
            cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})

            page.on("response", on_response)

            try:
                page.goto(
                    f"{self.BASE_URL}/f/{board}",
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
            except PWTimeout:
                pass  # SPA 仍會繼續執行，即使 domcontentloaded 較慢
            self._sleep()

            idle = 0
            last_count = 0
            max_scrolls = max(6, pages * 8)

            for index in range(max_scrolls):
                current = len(self._extract_posts(bodies))
                if current >= max_posts:
                    break

                page.mouse.wheel(0, 5000)
                self._sleep()

                if len(bodies) == last_count:
                    idle += 1
                    if idle >= 3:
                        break  # 連續數次沒有新資料，代表載完了
                else:
                    idle = 0
                    last_count = len(bodies)

                if progress_callback:
                    progress_callback({
                        "type": "crawler_progress",
                        "board": board,
                        "current_page": index + 1,
                        "total_pages": max_scrolls,
                        "crawled_count": current,
                        "progress": round(min(current / max_posts, 1) * 100, 2),
                    })
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            playwright.stop()

        posts = self._extract_posts(bodies)[:max_posts]
        return [self._to_article(post, board) for post in posts]
