"""Mobile01 爬蟲（透過 Playwright 開真實瀏覽器擷取 HTML）。

為什麼不像 PTT 那樣直接用 requests？
Mobile01 位於 Akamai 之後，會在邊緣節點依 TLS 指紋擋掉自動化流量：
實測 requests 與 curl 都直接回 403 Access Denied，即使補齊瀏覽器 headers 也一樣。
因此改用 Playwright 開真實瀏覽器取得頁面，再用 BeautifulSoup 解析 HTML
（不需要像 Dcard 那樣攔截 API，Mobile01 的內容就在 HTML 裡）。

資料路徑（實測）：
- 文章列表：topiclist.php?f={forum_id}&p={page}
             → .l-listTable__tr（標題 a.c-link.u-ellipsis、作者 a.u-username、
               發表時間 .l-listTable__td--time、回覆數 .l-listTable__td--count）
- 內文與回覆：topicdetail.php?f={forum_id}&t={topic_id}
             → 多個 <article>，第一個是主文，其餘為回覆

輸出欄位對齊 PTTCrawler / DcardCrawler，下游流程（relevance_filter →
create_article → Gemini 情緒評分）完全不需修改。

注意：
- board 使用「看板編號」字串（例如 371 = 彩妝保養），與網址一致。
- push_count 對應「回覆數」，作為互動熱度指標。
- 回覆預設併入內文（【留言】段落），讓情緒與關鍵字分析涵蓋討論串的聲音。
"""

import hashlib
import random
import re
import time
from datetime import datetime
from typing import Callable, Optional

from bs4 import BeautifulSoup


class Mobile01Crawler:
    """負責爬取 Mobile01 討論區的文章。"""

    BASE_URL = "https://www.mobile01.com"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    STEALTH_JS = (
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        "Object.defineProperty(navigator, 'languages', {get: () => ['zh-TW','zh','en']});"
        "window.chrome = { runtime: {} };"
    )

    def __init__(
        self,
        headless: bool = False,
        min_delay: float = 1.5,
        max_delay: float = 3.0,
        fetch_replies: bool = True,
        max_replies: int = 10,
    ):
        # Akamai 會擋無頭瀏覽器，預設開真實視窗。
        self.headless = headless
        self.min_delay = min_delay
        self.max_delay = max_delay
        # 是否把回覆併入內文一起分析。
        self.fetch_replies = fetch_replies
        self.max_replies = max_replies

    # ── 純函式工具（不需瀏覽器，便於單元測試） ──────────────────

    def _generate_unique_id(self, platform: str, board: str, url: str) -> str:
        """產生文章唯一 ID，讓重複爬取時能判斷是否已存在（與其他平台一致）。"""
        raw_text = f"{platform}:{board}:{url}"
        return hashlib.md5(raw_text.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_dt(text: str | None) -> Optional[datetime]:
        """從列表列的文字中取出發表時間，例如 '...2026-08-17 16:43'。"""
        if not text or not isinstance(text, str):
            return None

        match = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", text)
        if not match:
            return None

        try:
            return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None

    @staticmethod
    def _parse_reply_count(text: str | None) -> int:
        """把回覆數文字轉成整數，取不到就當 0。"""
        if not text:
            return 0

        digits = re.sub(r"[^\d]", "", str(text))
        return int(digits) if digits else 0

    @staticmethod
    def _clean_content(text: str | None) -> str:
        """整理擷取到的文字：去除前後空白、壓縮多餘空行。"""
        if not text:
            return ""

        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    @staticmethod
    def _merge_content_and_replies(content: str | None, replies: list[str]) -> str:
        """把主文與回覆合併成一段供分析的文字（回覆放在「【留言】」段落下）。"""
        parts: list[str] = []

        if content:
            parts.append(content.strip())

        if replies:
            parts.append("【留言】")
            parts.extend(f"- {reply}" for reply in replies)

        return "\n".join(parts).strip()

    def parse_topic_list(self, html: str, board: str) -> list[dict]:
        """解析討論區列表頁，回傳每篇文章的基本資訊（不含內文）。"""
        soup = BeautifulSoup(html, "html.parser")
        topics: list[dict] = []
        seen: set = set()

        for row in soup.select(".l-listTable__tr"):
            # 標題連結；作者連結同樣有 c-link u-ellipsis，需排除 u-username。
            title_link = None

            for link in row.select("a.c-link.u-ellipsis"):
                classes = link.get("class") or []

                if "u-username" in classes:
                    continue

                if "topicdetail.php" in (link.get("href") or ""):
                    title_link = link
                    break

            if title_link is None:
                continue  # 表頭或廣告列

            href = (title_link.get("href") or "").lstrip("/")
            url = f"{self.BASE_URL}/{href}"

            if url in seen:
                continue

            seen.add(url)

            author_link = row.select_one("a.u-username")
            author = author_link.get_text(strip=True) if author_link else "unknown"

            # 第一個 --time 欄位是「原發表者 + 發表時間」（第二個是最後回覆）。
            time_cell = row.select_one(".l-listTable__td--time")
            published_at = self._parse_dt(time_cell.get_text(" ", strip=True) if time_cell else None)

            count_cell = row.select_one(".l-listTable__td--count")
            reply_count = self._parse_reply_count(count_cell.get_text(strip=True) if count_cell else None)

            topics.append({
                "platform_name": "mobile01",
                "board_name": board,
                "author_username": author or "unknown",
                "title": title_link.get_text(strip=True),
                "url": url,
                "push_count": reply_count,
                "published_at": published_at,
                "unique_id": self._generate_unique_id("mobile01", board, url),
            })

        return topics

    def parse_topic_detail(self, html: str) -> tuple[str, list[str]]:
        """解析文章頁，回傳 (主文內容, 回覆文字清單)。"""
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select("article")

        if not articles:
            return "", []

        content = self._clean_content(articles[0].get_text("\n", strip=True))

        replies: list[str] = []

        if self.fetch_replies:
            for element in articles[1:]:
                text = self._clean_content(element.get_text("\n", strip=True))

                if text:
                    replies.append(text)

        return content, replies[: self.max_replies]

    def _sleep(self) -> None:
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    # ── 瀏覽器驅動的爬取 ────────────────────────────────────────

    def crawl_board(
        self,
        board: str = "371",
        pages: int = 1,
        start_page: int | None = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> list[dict]:
        """爬取一個 Mobile01 討論區。

        參數對齊其他爬蟲：
        - board：看板編號字串（371 = 彩妝保養、373 = 時尚流行）。
        - pages：要爬幾頁列表。
        - start_page：從第幾頁開始，預設第 1 頁。
        - progress_callback：回報進度（給 WebSocket 用）。
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "Mobile01 爬蟲需要 Playwright，請先安裝："
                "pip install playwright 並執行 playwright install chromium"
            ) from error

        first_page = start_page or 1
        articles: list[dict] = []

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

            topics: list[dict] = []

            for offset in range(max(1, pages)):
                page_no = first_page + offset
                url = f"{self.BASE_URL}/topiclist.php?f={board}&p={page_no}"

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                except Exception:
                    break  # 這一頁載入失敗就停止，保留已取得的資料

                self._sleep()
                found = self.parse_topic_list(page.content(), board)

                if not found:
                    break  # 沒有資料代表超出頁數範圍

                topics.extend(found)

            # 逐篇進入內頁取得主文與回覆
            total = len(topics)

            for index, topic in enumerate(topics):
                content, replies = "", []

                try:
                    page.goto(topic["url"], wait_until="domcontentloaded", timeout=60_000)
                    self._sleep()
                    content, replies = self.parse_topic_detail(page.content())
                except Exception:
                    pass  # 單篇失敗不影響整體，內文留空

                topic["content"] = self._merge_content_and_replies(content, replies)
                articles.append(topic)

                if progress_callback:
                    progress_callback({
                        "type": "crawler_progress",
                        "board": board,
                        "current_page": index + 1,
                        "total_pages": total,
                        "crawled_count": index + 1,
                        "progress": round((index + 1) / total * 100, 2) if total else 100.0,
                    })
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass

            playwright.stop()

        return articles
