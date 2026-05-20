import hashlib
import random
import time
from datetime import datetime
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup

class PTTCrawler:
    """
    PTTCrawler dùng để crawl bài viết từ PTT.

    Nhiệm vụ chính:
    1. Tạo session có cookie over18=1 để vượt qua trang xác nhận tuổi.
    2. Crawl danh sách bài viết từ board.
    3. Crawl nội dung chi tiết của từng bài.
    4. Chuẩn hóa dữ liệu để lưu vào database.
    """

    BASE_URL = "https://www.ptt.cc"

    def __init__(self):
        # Tạo HTTP session để tái sử dụng cookie và header giữa nhiều request.
        self.session = requests.Session()

        # PTT một số board cần xác nhận 18 tuổi.
        # Nếu không set cookie này, crawler có thể bị redirect về trang over18.
        self.session.cookies.set("over18", "1")

        # Danh sách User-Agent dùng random để request giống trình duyệt thật hơn.
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

        # 去掉 PTT 常見的分隔線。
        content = content.split("--")[0].strip()

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

        # Nếu không truyền start_page, bắt đầu từ trang mới nhất.
        # Ví dụ: https://www.ptt.cc/bbs/BeautySalon/index.html
        if start_page is None:
            current_url = f"{self.BASE_URL}/bbs/{board}/index.html"

        # Nếu có truyền start_page, bắt đầu từ trang cụ thể.
        # Ví dụ: start_page=3950
        # URL sẽ là https://www.ptt.cc/bbs/BeautySalon/index3950.html
        else:
            current_url = f"{self.BASE_URL}/bbs/{board}/index{start_page}.html"

        for page in range(pages):
            html = self._safe_get(current_url)

            if not html:
                break

            # Parse danh sách bài viết ở trang hiện tại.
            articles = self.parse_article_list(board, current_url)

            # Đi vào từng bài để lấy nội dung chi tiết.
            for article in articles:
                detail = self.parse_article_detail(article["url"])

                article["content"] = detail["content"]
                article["published_at"] = detail["published_at"]

                all_articles.append(article)

                # Random delay để giảm áp lực lên PTT.
                time.sleep(random.uniform(0.8, 1.5))

            # Sau khi crawl xong một trang, tìm link "上頁".
            # "上頁" trên PTT nghĩa là trang cũ hơn một bậc.
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

            # Nếu không tìm thấy 上頁 thì dừng crawler.
            if not previous_page_url:
                break

            # Cập nhật URL để vòng lặp kế tiếp crawl trang cũ hơn.
            current_url = previous_page_url

        return all_articles
        
    def get_latest_page_number(self, board: str) -> int | None:
        """
        Lấy số trang gần mới nhất của PTT board.

        Lưu ý:
            index.html là trang mới nhất nhưng không có số.
            Link "上頁" thường là indexN.html.
            Vậy N + 1 có thể xem là số trang mới nhất hiện tại.

        Ví dụ:
            index.html có 上頁 = index3950.html
            thì trang mới nhất tương đương khoảng 3951.
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

                # href thường có dạng /bbs/BeautySalon/index3950.html
                # Ta lấy số 3950 ra.
                import re
                match = re.search(r"index(\d+)\.html", href)

                if match:
                    previous_page_number = int(match.group(1))

                    # Vì 上頁 là trang ngay trước trang mới nhất,
                    # nên số trang mới nhất có thể xem là previous + 1.
                    return previous_page_number + 1

        return None
    
