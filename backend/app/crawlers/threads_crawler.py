"""Threads 爬蟲（透過 Playwright 開真實瀏覽器讀取「搜尋結果」）。

為什麼用搜尋頁而不是看板？
Threads 沒有看板（board）概念，內容以「關鍵字搜尋」為主要入口。
實測（2026）：
- ✅ /search?q={關鍵字} 在「未登入」狀態就能看到真實貼文 → 不需要帳號，
     也就沒有帳號被封鎖的風險。
- ❌ /tag/{關鍵字} 未登入會顯示「查無結果」並要求登入，因此不採用。
- 內容由 JS 動態渲染且 class 名稱經過混淆，所以用 Playwright 取得頁面後，
  以「貼文永久連結 a[href*='/post/']」為錨點往上找容器來擷取內容。

資料路徑（實測）：
- 搜尋結果：/search?q={keyword}&serp_type=default
             → a[href="/@{使用者}/post/{貼文ID}"]（永久連結）
             → 容器內含 <time datetime="ISO 時間"> 與貼文文字

輸出欄位對齊其他爬蟲，下游流程（relevance_filter → create_article →
Gemini 情緒評分）完全不需修改。

注意：
- board 存「搜尋關鍵字」（例如 醫美），因為 Threads 以關鍵字而非看板組織內容。
- 同一篇貼文可能同時符合多個關鍵字，因此 unique_id 只用貼文網址計算，
  避免同一篇文章被不同關鍵字重複收錄。
- push_count 取「讚 / 回覆 / 轉發」中的最大值，作為互動熱度指標。
"""

import hashlib
import random
import re
import time
import urllib.parse
from datetime import datetime
from typing import Callable, Optional


class ThreadsCrawler:
    """負責爬取 Threads 搜尋結果的貼文。"""

    BASE_URL = "https://www.threads.com"

    # 每次往下捲動大約多載入幾則貼文，用來把 pages 換算成目標貼文數。
    POSTS_PER_PAGE = 25

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    STEALTH_JS = (
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        "Object.defineProperty(navigator, 'languages', {get: () => ['zh-TW','zh','en']});"
        "window.chrome = { runtime: {} };"
    )

    # 擷取貼文的 JS：以永久連結為錨點，往上找到含有足夠文字的容器。
    EXTRACT_JS = """() => {
      const seen = new Set();
      const out = [];

      document.querySelectorAll('a[href*="/post/"]').forEach((a) => {
        const href = a.getAttribute('href');
        if (!href || seen.has(href)) return;
        seen.add(href);

        let node = a;
        for (let i = 0; i < 10 && node; i++) {
          const text = (node.innerText || '').trim();
          if (text.length > 60) break;
          node = node.parentElement;
        }

        const timeEl = (node || a).querySelector('time');
        out.push({
          url: href,
          user: (href.split('/')[1] || '').replace('@', ''),
          datetime: timeEl ? timeEl.getAttribute('datetime') : null,
          raw_text: node ? node.innerText : '',
        });
      });

      return out;
    }"""

    # 貼文文字裡的相對時間行，例如 9小時、2天、剛剛。
    RELATIVE_TIME_RE = re.compile(r"^\d+\s*(秒|分鐘|分|小時|天|週|周|個月|月|年)$|^剛剛$")

    def __init__(self, headless: bool = False, min_delay: float = 1.5, max_delay: float = 3.0):
        # Threads 由 Meta 營運，對自動化較敏感；預設開真實視窗較穩定。
        self.headless = headless
        self.min_delay = min_delay
        self.max_delay = max_delay

    # ── 純函式工具（不需瀏覽器，便於單元測試） ──────────────────

    @staticmethod
    def _generate_unique_id(url: str) -> str:
        """以貼文網址產生唯一 ID。

        刻意不含搜尋關鍵字：同一篇貼文可能同時出現在多個關鍵字的搜尋結果中，
        若把關鍵字算進去，同一篇文章會被重複寫入資料庫。
        """
        return hashlib.md5(f"threads:{url}".encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_dt(value: str | None) -> Optional[datetime]:
        """解析 <time datetime> 的 ISO 時間（例如 2026-08-19T06:35:40.000Z）。"""
        if not value or not isinstance(value, str):
            return None

        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

        # 統一存成不帶時區的 datetime，與其他平台一致。
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)

        return parsed

    @classmethod
    def _split_text_and_counts(
        cls,
        raw_text: str | None,
        username: str = "",
        keyword: str = "",
    ) -> tuple[str, int]:
        """把貼文區塊的文字拆成 (乾淨內文, 互動數)。

        Threads 的區塊文字大致長這樣：
            使用者名稱 / 主題標籤 / 相對時間 / 內文… / 翻譯 / 數字 / 數字 / 數字
        因此移除開頭的使用者名稱、主題標籤與相對時間，並在「翻譯」之後把數字
        視為讚 / 回覆 / 轉發，取最大值當熱度。
        """
        if not raw_text:
            return "", 0

        lines = [line.strip() for line in raw_text.splitlines()]
        lines = [line for line in lines if line]

        content_lines: list[str] = []
        counts: list[int] = []
        after_translate = False

        for index, line in enumerate(lines):
            # 開頭的使用者名稱與主題標籤都不是內文。
            if index == 0 and username and line == username:
                continue

            # 第 2 行常是搜尋關鍵字的主題標籤（例如「醫美」），不是貼文內容。
            if index <= 1 and keyword and line == keyword:
                continue

            if cls.RELATIVE_TIME_RE.match(line):
                continue

            if line == "翻譯":
                after_translate = True
                continue

            number = line.replace(",", "")

            if after_translate and number.isdigit():
                counts.append(int(number))
                continue

            if not after_translate:
                content_lines.append(line)

        # 沒有「翻譯」時，把結尾連續的純數字視為互動數。
        if not after_translate:
            while content_lines and content_lines[-1].replace(",", "").isdigit():
                counts.append(int(content_lines.pop().replace(",", "")))

        return "\n".join(content_lines).strip(), max(counts) if counts else 0

    def _to_article(self, post: dict, keyword: str) -> dict:
        """把擷取到的貼文轉成本專案統一的文章 dict。"""
        url_path = post.get("url") or ""
        url = f"{self.BASE_URL}{url_path}" if url_path.startswith("/") else url_path
        username = (post.get("user") or "").strip()
        content, push_count = self._split_text_and_counts(
            post.get("raw_text"), username, keyword
        )

        # Threads 貼文沒有標題，取內文第一行（過長就截斷）當標題。
        first_line = content.splitlines()[0] if content else ""
        title = first_line[:80] or f"{username} 的貼文"

        return {
            "platform_name": "threads",
            "board_name": keyword,
            "author_username": username or "unknown",
            "title": title,
            "content": content,
            "url": url,
            "push_count": push_count,
            "published_at": self._parse_dt(post.get("datetime")),
            "unique_id": self._generate_unique_id(url),
        }

    def _sleep(self) -> None:
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    # ── 瀏覽器驅動的爬取 ────────────────────────────────────────

    def crawl_board(
        self,
        board: str = "醫美",
        pages: int = 1,
        start_page: int | None = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[dict]:
        """以關鍵字搜尋 Threads，回傳貼文清單。

        參數對齊其他爬蟲：
        - board：搜尋關鍵字（Threads 沒有看板概念）。
        - pages：以「頁」為單位，內部換算為 pages × POSTS_PER_PAGE 則目標貼文。
        - start_page：Threads 為無限捲軸，保留參數但忽略。
        - progress_callback：回報進度（給 WebSocket 用）。
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "Threads 爬蟲需要 Playwright，請先安裝："
                "pip install playwright 並執行 playwright install chromium"
            ) from error

        max_posts = max(1, pages) * self.POSTS_PER_PAGE
        keyword = board
        posts: list[dict] = []

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

            query = urllib.parse.quote(keyword)
            url = f"{self.BASE_URL}/search?q={query}&serp_type=default"

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            except Exception:
                pass  # SPA 仍會繼續載入

            try:
                # 等到第一則貼文的永久連結出現，代表搜尋結果已渲染。
                page.wait_for_selector('a[href*="/post/"]', timeout=30_000)
            except Exception:
                return []  # 沒有結果或被擋，回傳空清單

            self._sleep()

            idle = 0
            last_count = 0
            max_scrolls = max(6, pages * 8)

            for index in range(max_scrolls):
                try:
                    posts = page.evaluate(self.EXTRACT_JS)
                except Exception:
                    break

                if len(posts) >= max_posts:
                    break

                if len(posts) == last_count:
                    idle += 1
                    if idle >= 3:
                        break  # 連續捲動都沒有新貼文，代表載完了
                else:
                    idle = 0
                    last_count = len(posts)

                page.mouse.wheel(0, 5000)
                self._sleep()

                if progress_callback:
                    progress_callback({
                        "type": "crawler_progress",
                        "board": keyword,
                        "current_page": index + 1,
                        "total_pages": max_scrolls,
                        "crawled_count": len(posts),
                        "progress": round(min(len(posts) / max_posts, 1) * 100, 2),
                    })

            try:
                posts = page.evaluate(self.EXTRACT_JS)
            except Exception:
                pass
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass

            playwright.stop()

        return [self._to_article(post, keyword) for post in posts[:max_posts]]
