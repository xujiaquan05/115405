import hashlib
import random
import re
import time
from datetime import datetime
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup

class PTTCrawler:
    """
    PTTCrawler 負責爬取 PTT 文章。

    主要工作：
    1. 建立帶 over18=1 cookie 的 session，通過年齡確認頁。
    2. 爬取看板的文章列表。
    3. 爬取每篇文章的詳細內容。
    4. 把資料整理成可存入 database 的格式。
    """

    BASE_URL = "https://www.ptt.cc"

    # 說明：
    # 這些標題屬於版務/公告類文章，和消費者輿情無關。
    # 在「列表頁」就先過濾掉，好處有兩個：
    # 1. 不用進入內頁抓詳細內容（每篇省下約 1~1.5 秒的延遲）。
    # 2. 資料庫不會被版規、公告、水桶名單等雜訊污染，
    #    後續 LLM 分析的輸入更乾淨。
    JUNK_TITLE_KEYWORDS = [
        "[公告]",
        "(公告)",
        "[版務]",
        "[板務]",
        "[版規]",
        "[板規]",
        "[水桶]",
        "[置底]",
        "[申訴]",
        "[檢舉]",
        "[投票]",
        "[樂透]",
    ]

    def __init__(self):
        # 建立 HTTP session，讓多個 request 共用 cookie 和 header。
        self.session = requests.Session()

        # PTT 部分看板需要確認滿 18 歲。
        # 不設定這個 cookie 的話，crawler 會被導回 over18 確認頁。
        self.session.cookies.set("over18", "1")

        # 隨機使用不同 User-Agent，讓 request 更像真實瀏覽器。
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        ]

    def _get_headers(self):
        """
        每次 request 隨機選一個 User-Agent。

        為什麼要這樣做？
        因為如果所有 request 都長得一樣，比較容易被網站判斷成機器人。
        """
        return {
            "User-Agent": random.choice(self.user_agents)
        }

    def _safe_get(self, url: str, retries: int = 3) -> Optional[str]:
        """
        安全發送 GET request。

        retries:
            最多重試次數。

        為什麼需要重試？
        網路可能暫時不穩，PTT 也可能偶爾回應失敗。
        如果不重試，crawler 很容易因為一次小錯誤就中斷。
        """
        for attempt in range(retries):
            try:
                response = self.session.get(
                    url,
                    headers=self._get_headers(),
                    timeout=10
                )

                # HTTP 200 代表成功取得頁面。
                if response.status_code == 200:
                    response.encoding = "utf-8"
                    return response.text

                # HTTP 429 代表請求太頻繁。
                # 遇到這種狀況要等久一點，避免造成網站壓力。
                if response.status_code == 429:
                    wait_seconds = random.uniform(10, 30)
                    time.sleep(wait_seconds)

            except requests.RequestException:
                # 指數退避：第 1 次等 1 秒，第 2 次等 2 秒，第 3 次等 4 秒。
                time.sleep(2 ** attempt)

        # 如果重試後仍失敗，回傳 None。
        return None

    def _parse_push_count(self, push_text: str) -> int:
        """
        解析 PTT 推文數。

        PTT 推文數可能是：
        - 數字，例如 10
        - 爆，代表很熱門，這裡轉成 100
        - X1, X2，代表負推，這裡轉成負數
        - 空白，代表 0
        """
        push_text = push_text.strip()

        if not push_text:
            return 0

        if push_text == "爆":
            return 100

        if push_text.startswith("X"):
            try:
                return -int(push_text.replace("X", ""))
            except ValueError:
                return 0

        try:
            return int(push_text)
        except ValueError:
            return 0

    def _is_junk_title(self, title: str) -> bool:
        """
        判斷標題是否屬於版務/公告類雜訊文章。
        """

        return any(keyword in title for keyword in self.JUNK_TITLE_KEYWORDS)

    def _generate_unique_id(self, platform: str, board: str, url: str) -> str:
        """
        產生文章唯一 ID。

        為什麼要做 unique_id？
        因為 crawler 重複跑時，很可能再次抓到同一篇文章。
        unique_id 可以讓 database 判斷文章是否已經存在，避免重複儲存。
        """
        raw_text = f"{platform}:{board}:{url}"
        return hashlib.md5(raw_text.encode("utf-8")).hexdigest()

    def parse_article_list(self, board: str, page_url: str):
        """
        解析 PTT board 列表頁。

        回傳格式：
        [
            {
                "title": "...",
                "author": "...",
                "url": "...",
                "push_count": 10
            }
        ]
        """
        html = self._safe_get(page_url)

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")

        articles = []

        # PTT 每一篇文章在列表頁通常是 div.r-ent
        entries = soup.select("div.r-ent")

        for entry in entries:
            title_tag = entry.select_one("div.title a")

            # 如果 title 沒有 a，通常代表文章已刪除。
            # 這種文章沒有內文 URL，所以直接跳過。
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)

            # 版務/公告類文章直接跳過，不進內頁、不入庫。
            if self._is_junk_title(title):
                continue

            article_url = self.BASE_URL + title_tag["href"]

            author_tag = entry.select_one("div.author")
            author = author_tag.get_text(strip=True) if author_tag else "unknown"

            push_tag = entry.select_one("div.nrec")
            push_text = push_tag.get_text(strip=True) if push_tag else ""
            push_count = self._parse_push_count(push_text)

            articles.append({
                "platform_name": "ptt",
                "board_name": board,
                "author_username": author,
                "title": title,
                "url": article_url,
                "push_count": push_count,
                "unique_id": self._generate_unique_id("ptt", board, article_url),
            })

        return articles

    def parse_article_detail(self, article_url: str):
        """
        解析文章內頁，取得乾淨的文章內容與發文時間。

        為什麼不能直接取全文？
        因為 PTT 文章頁裡面包含：
        - 作者資訊
        - 標題資訊
        - 時間資訊
        - 推文內容
        這些不一定都是文章正文，所以要先清理。
        """
        html = self._safe_get(article_url)

        if not html:
            return {
                "content": "",
                "published_at": None
            }

        soup = BeautifulSoup(html, "html.parser")
        main_content = soup.select_one("#main-content")

        if not main_content:
            return {
                "content": "",
                "published_at": None
            }

        # 先嘗試從 meta-value 取得發文時間。
        meta_values = main_content.select("span.article-meta-value")
        published_at = None

        # PTT meta 通常順序是：作者、看板、標題、時間
        if len(meta_values) >= 4:
            time_text = meta_values[3].get_text(strip=True)
            published_at = self._parse_ptt_time(time_text)

        # 移除 meta 資訊，避免混入正文。
        for tag in main_content.select("div.article-metaline"):
            tag.decompose()

        for tag in main_content.select("div.article-metaline-right"):
            tag.decompose()

        # 移除推文區塊。
        for tag in main_content.select("div.push"):
            tag.decompose()

        # 取得清理後的文字。
        content = main_content.get_text("\n", strip=True)

        # PTT 簽名檔以「獨立一行 --」開始，之後接簽名與 ※ 發信站資訊。
        # 只能從「最後一個」獨立 -- 行切開；
        # 如果像舊版一樣用 content.split("--")，
        # 正文中含 "--" 的網址或分隔線都會把文章誤切一半。
        signature_parts = re.split(r"\n--\s*(?:\n|$)", content)

        if len(signature_parts) > 1:
            content = "\n--\n".join(signature_parts[:-1])

        content = content.strip()

        return {
            "content": content,
            "published_at": published_at
        }

    def _parse_ptt_time(self, time_text: str):
        """
        解析 PTT 的英文時間格式。

        範例：
        Mon Jan  1 12:00:00 2024
        """
        try:
            return datetime.strptime(time_text, "%a %b %d %H:%M:%S %Y")
        except ValueError:
            return None

    def crawl_board(
    self,
    board: str = "BeautySalon",
    pages: int = 1,
    start_page: int | None = None,
    progress_callback: Optional[Callable[[dict], None]] = None
):
    
        all_articles = []

        # 沒有指定 start_page 時，從最新一頁開始。
        # 例如：https://www.ptt.cc/bbs/BeautySalon/index.html
        if start_page is None:
            current_url = f"{self.BASE_URL}/bbs/{board}/index.html"

        # 有指定 start_page 時，從指定頁開始。
        # 例如：start_page=3950
        # URL 為 https://www.ptt.cc/bbs/BeautySalon/index3950.html
        else:
            current_url = f"{self.BASE_URL}/bbs/{board}/index{start_page}.html"

        for page in range(pages):
            html = self._safe_get(current_url)

            if not html:
                break

            # 解析目前頁面的文章列表。
            articles = self.parse_article_list(board, current_url)

            # 進入每一篇文章抓取詳細內容。
            for article in articles:
                detail = self.parse_article_detail(article["url"])

                article["content"] = detail["content"]
                article["published_at"] = detail["published_at"]

                all_articles.append(article)

                # 隨機延遲，減少對 PTT 的壓力。
                time.sleep(random.uniform(0.8, 1.5))

            # 爬完一頁後尋找「上頁」連結，
            # 「上頁」代表更舊一頁的列表。
            if progress_callback:
                progress_callback({
                    "type": "crawler_progress",
                    "board": board,
                    "current_page": page + 1,
                    "total_pages": pages,
                    "crawled_count": len(all_articles),
                    "progress": round(((page + 1) / pages) * 100, 2),
                })

            soup = BeautifulSoup(html, "html.parser")
            paging_links = soup.select("div.btn-group-paging a")

            previous_page_url = None

            for link in paging_links:
                link_text = link.get_text(strip=True)

                if "上頁" in link_text:
                    previous_page_url = self.BASE_URL + link["href"]
                    break

            # 找不到「上頁」就停止爬取。
            if not previous_page_url:
                break

            # 更新 URL，下一輪迴圈爬更舊的一頁。
            current_url = previous_page_url

        return all_articles
        
    def get_latest_page_number(self, board: str) -> int | None:
        """
        取得 PTT 看板目前最新的頁碼。

        說明：
            index.html 是最新頁，但網址沒有頁碼。
            「上頁」連結通常是 indexN.html，
            所以 N + 1 可視為目前最新的頁碼。

        例如：
            index.html 的上頁是 index3950.html，
            最新頁大約就是 3951。
        """

        latest_url = f"{self.BASE_URL}/bbs/{board}/index.html"

        html = self._safe_get(latest_url)

        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        paging_links = soup.select("div.btn-group-paging a")

        for link in paging_links:
            link_text = link.get_text(strip=True)

            if "上頁" in link_text:
                href = link.get("href", "")

                # href 通常是 /bbs/BeautySalon/index3950.html，
                # 取出其中的數字 3950。
                match = re.search(r"index(\d+)\.html", href)

                if match:
                    previous_page_number = int(match.group(1))

                    # 「上頁」是最新頁的前一頁，
                    # 所以最新頁碼可視為 previous + 1。
                    return previous_page_number + 1

        return None
    
