import re
from zipfile import ZipFile

import pytest
from playwright.sync_api import expect

from system_tests.support import PASSWORD

pytestmark = pytest.mark.e2e


def login(page, username="alice"):
    page.goto("/login")
    page.get_by_label("帳號", exact=True).fill(username)
    page.get_by_label("密碼", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="登入", exact=True).click()
    expect(page).to_have_url("/dashboard")
    # Search through the UI; the dashboard's default terms do not match the fixtures.
    selected = page.locator(".keyword-token.selected")
    while selected.count():
        selected.first.click()
    page.get_by_placeholder("輸入其他關鍵字後按 Enter 新增").fill("玻尿酸")
    page.get_by_role("button", name="搜尋", exact=True).click()
    expect(page.locator(".article-table tbody tr")).to_have_count(2)


def test_login_cookie_persists_and_logout_revokes_browser_session(page):
    page.goto("/login")
    page.get_by_label("帳號", exact=True).fill("alice")
    page.get_by_label("密碼", exact=True).fill("wrong-password")
    page.get_by_role("button", name="登入", exact=True).click()
    expect(page.locator(".login-error")).to_contain_text("帳號或密碼錯誤")
    login(page)
    cookie = next(c for c in page.context.cookies() if c["name"] == "access_token")
    assert cookie["httpOnly"] is True
    assert cookie["sameSite"] == "Strict"
    page.reload()
    expect(page.get_by_role("button", name="登出", exact=True)).to_be_visible()
    assert page.request.get("/api/auth/me").status == 200
    page.get_by_role("button", name="登出", exact=True).click()
    expect(page).to_have_url("/login")
    assert page.request.get("/api/auth/me").status == 401


def test_search_filter_article_detail_and_excel_download(page, tmp_path):
    login(page)
    page.get_by_role("button", name="PTT", exact=True).click()
    expect(page.locator(".article-table tbody tr")).to_have_count(1)
    expect(page.locator(".article-table")).to_contain_text("E2E PTT")
    with page.expect_download() as download_info:
        page.get_by_role("button", name="匯出 Excel", exact=True).click()
    download = download_info.value
    assert download.suggested_filename.endswith(".xlsx")
    path = tmp_path / "articles.xlsx"
    download.save_as(path)
    with ZipFile(path) as workbook:
        sheet = workbook.read("xl/worksheets/sheet1.xml").decode()
        assert "E2E PTT" in sheet
        assert "E2E Dcard" not in sheet
    page.get_by_role("button", name="詳情", exact=True).click()
    expect(page).to_have_url(re.compile(r"/article/\d+$"))
    expect(page.get_by_role("heading", name="玻尿酸 E2E PTT 心得")).to_be_visible()
    expect(page.get_by_text("術後有點腫脹", exact=True)).to_be_visible()


def test_search_qa_history_and_report(page):
    login(page)
    page.get_by_role("button", name="搜尋", exact=True).click()
    expect(page.get_by_text("E2E 固定洞察：關注術後保濕與腫脹。", exact=True)).to_be_visible()
    page.get_by_role("link", name="AI 問答", exact=True).click()
    page.get_by_placeholder("問目前 Dashboard 的分析結果…（Enter 送出，Shift+Enter 換行）").fill("目前有哪些重點？")
    page.get_by_role("button", name="送出問題", exact=True).click()
    expect(page.get_by_text("E2E 固定回答：樣本提到保濕效果，應持續追蹤術後腫脹。", exact=True)).to_be_visible()
    assert page.request.get("/api/monitor/keywords").json()["data"]["plan"]["usage"]["qa_questions"] == 1
    page.get_by_role("link", name="History", exact=True).click()
    expect(page.locator(".history-page")).to_contain_text("玻尿酸")
    page.get_by_role("link", name="Dashboard", exact=True).click()
    page.get_by_role("button", name="匯出報告", exact=True).click()
    expect(page.locator(".report-doc")).to_contain_text("E2E 固定洞察")
    expect(page.get_by_role("button", name="列印 / 存成 PDF")).to_be_visible()


def test_guest_and_free_account_cannot_use_paid_features(page):
    page.goto("/login")
    page.get_by_role("button", name="以訪客身分瀏覽 Dashboard").click()
    expect(page).to_have_url("/dashboard")
    page.get_by_role("button", name="匯出 Excel", exact=True).click()
    expect(page.locator(".error-message")).to_contain_text("請先登入")
    page.get_by_role("link", name="AI 問答", exact=True).click()
    page.get_by_placeholder("問目前 Dashboard 的分析結果…（Enter 送出，Shift+Enter 換行）").fill("目前有哪些重點？")
    page.get_by_role("button", name="送出問題").click()
    expect(page.locator(".error-message")).to_contain_text("請先登入")
    login(page, "freeuser")
    page.get_by_role("button", name="匯出 Excel", exact=True).click()
    expect(page.locator(".error-message")).to_contain_text("未包含匯出")
    page.get_by_role("link", name="AI 問答", exact=True).click()
    page.get_by_placeholder("問目前 Dashboard 的分析結果…（Enter 送出，Shift+Enter 換行）").fill("目前有哪些重點？")
    page.get_by_role("button", name="送出問題").click()
    expect(page.locator(".error-message")).to_contain_text("未包含 AI 問答")
