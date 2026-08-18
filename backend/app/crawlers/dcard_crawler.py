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
- 完整內文：進入 /f/{alias}/p/{id} 貼文頁，從 DOM 的 <article> 取出全文
             （Dcard 沒有穩定的內文 API，改讀 DOM）。
- 留言（推文）：同一貼文頁 → 攔截回應 '/posts/{id}/comments'
             → { items: [...], nextKey }，往下捲動觸發載入更多。

為了讓下游流程（relevance_filter → create_article → Gemini 情緒評分）
不必修改，本爬蟲輸出的欄位刻意對齊 PTTCrawler：
    platform_name / board_name / author_username / title / content /
    url / push_count / published_at / unique_id

注意：
- Dcard 文章多為匿名，沒有帳號名稱；此處以「學校 or 匿名」當作者。
- push_count 對應 Dcard 的 likeCount（Dcard 沒有負推，皆為非負值）。
- 內文預設抓「完整全文」（fetch_full_content=True）：逐篇進入內頁讀取，
  分析更精準但較慢（每篇多花數秒）；讀取失敗時自動退回列表的 excerpt（摘要）。
  若要追求速度，可用 fetch_full_content=False 只取 excerpt。
- 留言預設一併抓取（fetch_comments=True）並「併入內文」一起分析，
  因此情緒評分、關鍵字雲與 LLM 洞察都會涵蓋留言區的聲音（輿情重點常在留言）。
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

    # 進內頁後，為了觸發 Dcard 無限捲軸載入留言，最多往下捲的次數。
    COMMENT_SCROLLS = 10

    def __init__(
        self,
        headless: bool = False,
        min_delay: float = 1.5,
        max_delay: float = 3.5,
        fetch_full_content: bool = True,
        fetch_comments: bool = True,
        max_comments: int = 20,
    ):
        # headless 預設 False：Dcard 會擋 headless。除非測試/特殊情況才開 True。
        self.headless = headless
        self.min_delay = min_delay
        self.max_delay = max_delay
        # fetch_full_content=True：逐篇進內頁抓完整內文（較慢但分析更準）；
        # False：只取列表的 excerpt（較快）。
        self.fetch_full_content = fetch_full_content
        # fetch_comments=True：進內頁時一併抓留言，併入內文一起分析
        # （情緒、關鍵字、LLM 洞察都會納入留言的聲音）。
        self.fetch_comments = fetch_comments
        # 每篇最多納入幾則留言（避免內文過長、拖慢爬取）。
        self.max_comments = max_comments

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

    @staticmethod
    def _pick_author(post: dict) -> str:
        """取出可顯示的作者名稱（學校 / 科系），沒有就回傳「Dcard 匿名」。

        注意：Dcard 的 anonymousSchool / anonymousDepartment 是「布林旗標」
        （代表是否匿名），不是名稱；直接拿來當作者會把 True 寫進資料庫，
        因此這裡只接受非空字串。
        """
        for key in ("school", "department"):
            value = post.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        return "Dcard 匿名"

    def _to_article(self, post: dict, board: str, content: str | None = None) -> dict:
        """把 Dcard 的 post 物件轉成本專案統一的文章 dict。

        content：若有傳入（進內頁抓到的完整全文）就採用；
        否則退回列表回傳的 excerpt（摘要）。
        """
        post_id = post.get("id")
        url = f"{self.BASE_URL}/f/{board}/p/{post_id}"
        author = self._pick_author(post)

        return {
            "platform_name": "dcard",
            "board_name": board,
            "author_username": author,
            "title": post.get("title") or "",
            "content": content or post.get("excerpt") or "",
            "url": url,
            "push_count": post.get("likeCount") or 0,
            "published_at": self._parse_dt(post.get("createdAt")),
            "unique_id": self._generate_unique_id("dcard", board, url),
        }

    @staticmethod
    def _clean_content(text: str | None) -> str:
        """整理從 DOM 取出的內文：去除前後空白、壓縮多餘空行。"""
        if not text:
            return ""
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    @staticmethod
    def _extract_comments(bodies: list) -> list[str]:
        """從多個 '/posts/{id}/comments' 回應中彙整留言文字（去重、去空）。

        Dcard 留言回應格式為 { items: [...], nextKey }，每則留言有 id 與 content；
        被刪除 / 隱藏的留言 content 可能為空，一律略過。
        """
        seen: set = set()
        comments: list[str] = []

        for body in bodies:
            if isinstance(body, dict):
                items = body.get("items")
            elif isinstance(body, list):
                items = body
            else:
                items = None

            if not isinstance(items, list):
                continue

            for c in items:
                if not isinstance(c, dict):
                    continue
                comment_id = c.get("id")
                text = (c.get("content") or "").strip()
                if not text or comment_id in seen:
                    continue
                seen.add(comment_id)
                comments.append(text)

        return comments

    @staticmethod
    def _merge_content_and_comments(content: str | None, comments: list[str]) -> str:
        """把內文與留言合併成一段供分析的文字（留言放在「【留言】」段落下）。"""
        parts: list[str] = []
        if content:
            parts.append(content.strip())
        if comments:
            parts.append("【留言】")
            parts.extend(f"- {c}" for c in comments)
        return "\n".join(parts).strip()

    def _fetch_post_detail(self, page, board: str, post_id) -> tuple[str | None, list[str]]:
        """進入單篇貼文頁，回傳 (完整內文, 留言文字清單)。

        - 內文：從 DOM 的 <article> 取出。
        - 留言：攔截 '/posts/{id}/comments' 回應，往下捲動觸發載入更多。
        任何錯誤都安全退回（內文 None、留言空清單），不影響整體爬取。
        """
        url = f"{self.BASE_URL}/f/{board}/p/{post_id}"
        comment_bodies: list = []

        def on_comment(resp):
            if f"/posts/{post_id}/comments" in resp.url:
                try:
                    comment_bodies.append(resp.json())
                except Exception:
                    pass  # 略過非 JSON 回應

        page.on("response", on_comment)

        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            except Exception:
                pass  # SPA 可能較慢，仍嘗試往下讀取

            try:
                page.wait_for_selector("article", timeout=15_000)
            except Exception:
                return None, []

            # 內文
            content = None
            try:
                element = page.query_selector("article")
                if element is not None:
                    content = self._clean_content(element.inner_text())
            except Exception:
                content = None

            # 留言：往下捲動觸發無限捲軸載入，直到夠數或不再增加
            comments: list[str] = []
            if self.fetch_comments:
                idle = 0
                last = 0
                for _ in range(self.COMMENT_SCROLLS):
                    if len(self._extract_comments(comment_bodies)) >= self.max_comments:
                        break
                    page.mouse.wheel(0, 6000)
                    self._sleep()
                    if len(comment_bodies) == last:
                        idle += 1
                        # 還沒收到任何留言回應時要多等幾輪：留言是延遲載入的，
                        # 太早判定「載完了」會導致大部分文章抓不到留言。
                        idle_limit = 2 if comment_bodies else 5
                        if idle >= idle_limit:
                            break  # 連續沒有新留言，代表載完了
                    else:
                        idle = 0
                        last = len(comment_bodies)
                comments = self._extract_comments(comment_bodies)[: self.max_comments]

            return content, comments
        finally:
            page.remove_listener("response", on_comment)

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
        articles: list = []

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

            posts = self._extract_posts(bodies)[:max_posts]

            if not self.fetch_full_content and not self.fetch_comments:
                # 快速模式：只用列表回傳的 excerpt 當內文。
                articles = [self._to_article(post, board) for post in posts]
            else:
                # 完整模式：逐篇進入內頁抓 <article> 全文與留言（較慢）。
                # 先停止監聽列表回應，避免內頁的 JSON 不斷累積。
                page.remove_listener("response", on_response)
                total = len(posts)

                for i, post in enumerate(posts):
                    detail_content, comments = self._fetch_post_detail(page, board, post.get("id"))
                    # 只要 fetch_full_content 關閉，就不採用內頁全文（改用 excerpt），
                    # 但仍可把留言併入分析。
                    base_content = detail_content if self.fetch_full_content else (post.get("excerpt") or "")
                    merged = self._merge_content_and_comments(base_content, comments)
                    articles.append(self._to_article(post, board, content=merged))
                    self._sleep()  # 禮貌性延遲，降低被 Dcard 擋的機率

                    if progress_callback:
                        progress_callback({
                            "type": "crawler_progress",
                            "board": board,
                            "current_page": i + 1,
                            "total_pages": total,
                            "crawled_count": i + 1,
                            "progress": round((i + 1) / total * 100, 2) if total else 100.0,
                        })
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            playwright.stop()

        return articles
