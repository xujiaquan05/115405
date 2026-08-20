"""以真實瀏覽器（Playwright）爬取的共用基底類別。

Dcard、Mobile01、Threads 都因為各自的原因無法用一般 HTTP request 取得內容：
- Dcard：Cloudflare 擋 headless，且 API 需由前端自己呼叫再攔截。
- Mobile01：Akamai 依 TLS 指紋擋掉 requests / curl（403）。
- Threads：內容由 JS 動態渲染。

三者的瀏覽器啟動流程與文字處理幾乎相同，集中在這裡避免重複，
各平台只需實作自己的「解析」邏輯。
"""

import hashlib
import random
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional


class BrowserCrawler:
    """需要真實瀏覽器的爬蟲共用基底。"""

    # 各平台自行覆寫。
    BASE_URL = ""

    # 用真實瀏覽器的 User-Agent，降低被判定為自動化的機率。
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    # 減少常被檢查的自動化痕跡。
    STEALTH_JS = (
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        "Object.defineProperty(navigator, 'languages', {get: () => ['zh-TW','zh','en']});"
        "window.chrome = { runtime: {} };"
    )

    def __init__(self, headless: bool = False, min_delay: float = 1.5, max_delay: float = 3.5):
        # 這些站台都會擋無頭瀏覽器，預設開真實視窗。
        self.headless = headless
        self.min_delay = min_delay
        self.max_delay = max_delay

    # ── 共用工具（不需瀏覽器，便於單元測試） ────────────────────

    def _sleep(self) -> None:
        """禮貌性隨機延遲，降低對來源站台的壓力。"""
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _generate_unique_id(self, platform: str, board: str, url: str) -> str:
        """產生文章唯一 ID，讓重複爬取時能判斷文章是否已存在。"""
        raw_text = f"{platform}:{board}:{url}"
        return hashlib.md5(raw_text.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_dt(value: str | None) -> Optional[datetime]:
        """解析 ISO 時間字串（例如 2026-08-19T06:35:40.000Z）。

        時間格式不同的平台（例如 Mobile01 是 2026-08-17 16:43）自行覆寫。
        """
        if not value or not isinstance(value, str):
            return None

        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

        # 統一存成不帶時區的 datetime，各平台一致。
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)

        return parsed

    @staticmethod
    def _clean_content(text: str | None) -> str:
        """整理擷取到的文字：去除前後空白、壓縮多餘空行。"""
        if not text:
            return ""

        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    @staticmethod
    def _merge_content_and_replies(content: str | None, replies: list[str]) -> str:
        """把主文與留言 / 回覆合併成一段供分析的文字。

        留言放在「【留言】」段落下，讓情緒、關鍵字與 LLM 分析
        也能涵蓋討論串裡的聲音（輿情重點常在留言）。
        """
        parts: list[str] = []

        if content:
            parts.append(content.strip())

        if replies:
            parts.append("【留言】")
            parts.extend(f"- {reply}" for reply in replies)

        return "\n".join(parts).strip()

    # ── 瀏覽器 ──────────────────────────────────────────────────

    @contextmanager
    def _open_page(self, disable_cache: bool = False):
        """開啟一個已套用 stealth 設定的瀏覽器分頁，離開時自動關閉。

        disable_cache=True 會關閉 HTTP 快取：攔截 API 回應時如果回應來自
        快取，Playwright 取不到 body，資料就會漏掉（Dcard 需要）。
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "此爬蟲需要 Playwright，請先安裝："
                "pip install playwright 並執行 playwright install chromium"
            ) from error

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

            if disable_cache:
                cdp = context.new_cdp_session(page)
                cdp.send("Network.enable")
                cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})

            yield page
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass

            playwright.stop()
