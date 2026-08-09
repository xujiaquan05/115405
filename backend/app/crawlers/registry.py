"""爬蟲註冊表：依平台名稱回傳對應的爬蟲實例。

新增平台時只要在這裡登記，crawler_router 與 scheduler 便能共用同一套分派邏輯。
DcardCrawler 於函式內延遲匯入，避免未安裝 Playwright 時影響其他平台。
"""

from app.crawlers.ptt_crawler import PTTCrawler


def get_crawler(platform_name: str):
    """依平台名稱建立對應爬蟲；未知平台一律退回 PTT。"""
    if platform_name == "dcard":
        from app.crawlers.dcard_crawler import DcardCrawler

        return DcardCrawler()

    return PTTCrawler()
