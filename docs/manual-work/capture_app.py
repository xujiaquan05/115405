import os
import sys
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))
os.environ.update(DATABASE_URL='sqlite://', PYTHON_DOTENV_DISABLED='1', GOOGLE_API_KEY='', PBKDF2_ITERATIONS='1000', JWT_SECRET='manual-fixture-only-not-for-production')
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(BACKEND / '.test-artifacts/browsers')
from scripts.run_system_tests import local_postgres, free_port
from system_tests.support import disposable_database, migrate, seed_data, test_environment, PASSWORD
from sqlalchemy import create_engine
from playwright.sync_api import sync_playwright, expect
import httpx

OUT = ROOT / 'docs/manual-work/screens'
OUT.mkdir(exist_ok=True)
with local_postgres() as admin_url, disposable_database(admin_url) as url:
    migrate(url)
    engine = create_engine(url)
    seed_data(engine)
    from sqlalchemy.orm import Session
    from app.models.database_models import User
    from app.services.auth_service import hash_password
    with Session(engine) as db:
        db.add(User(username='admin', password_hash=hash_password(PASSWORD), display_name='系統管理員', role='admin', is_active=1, plan_code='business'))
        db.commit()
    engine.dispose()
    port = free_port()
    env = {**test_environment(url), 'TEST_POSTGRES_URL': admin_url}
    with (OUT / 'server.log').open('w', encoding='utf-8') as log:
        proc = subprocess.Popen([sys.executable, '-m', 'system_tests.e2e_server', '--port', str(port)], cwd=BACKEND, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            base = f'http://127.0.0.1:{port}'
            for _ in range(150):
                try:
                    if httpx.get(base+'/health', timeout=1, trust_env=False).status_code == 200: break
                except httpx.HTTPError: pass
                time.sleep(.2)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(base_url=base, viewport={'width':1440,'height':1050}, device_scale_factor=1)
                def shot(name):
                    page.screenshot(path=str(OUT / (name+'.png')), full_page=False)
                page.goto('/')
                shot('01_home')
                page.goto('/login')
                shot('02_login')
                page.get_by_label('帳號',exact=True).fill('alice')
                page.get_by_label('密碼',exact=True).fill(PASSWORD)
                page.get_by_role('button',name='登入',exact=True).click()
                expect(page).to_have_url(base+'/dashboard')
                tokens=page.locator('.keyword-token.selected')
                while tokens.count(): tokens.first.click()
                page.get_by_placeholder('輸入其他關鍵字後按 Enter 新增').fill('玻尿酸')
                page.get_by_role('button',name='搜尋',exact=True).click()
                expect(page.locator('.article-table tbody tr')).to_have_count(2)
                expect(page.get_by_text('E2E 固定洞察：關注術後保濕與腫脹。',exact=True)).to_be_visible()
                shot('03_dashboard')
                page.locator('.article-table').screenshot(path=str(OUT/'04_articles.png'))
                page.get_by_role('button',name='詳情',exact=True).first.click()
                expect(page.get_by_text('術後有點腫脹',exact=True)).to_be_visible()
                shot('05_detail')
                page.goto('/qa')
                page.get_by_placeholder('問目前 Dashboard 的分析結果…（Enter 送出，Shift+Enter 換行）').fill('目前有哪些重點？')
                page.get_by_role('button',name='送出問題',exact=True).click()
                expect(page.get_by_text('E2E 固定回答：樣本提到保濕效果，應持續追蹤術後腫脹。',exact=True)).to_be_visible()
                shot('06_qa')
                for route,name in [('/history','07_history'),('/monitor','08_monitor'),('/profile','09_profile')]:
                    page.goto(route); page.wait_for_load_state('networkidle'); shot(name)
                page.goto('/dashboard')
                page.wait_for_load_state('networkidle')
                page.get_by_role('button',name='匯出報告',exact=True).click()
                expect(page.locator('.report-doc')).to_be_visible(); shot('10_report')
                page.get_by_role('button',name='登出',exact=True).click()
                expect(page).to_have_url(base+'/login')
                page.get_by_label('帳號',exact=True).fill('admin')
                page.get_by_label('密碼',exact=True).fill(PASSWORD)
                page.get_by_role('button',name='登入',exact=True).click()
                expect(page).to_have_url(base+'/dashboard')
                for route,name in [('/admin/users','11_users'),('/admin/system','12_system'),('/crawl','13_crawl')]:
                    page.goto(route); page.wait_for_load_state('networkidle'); shot(name)
                browser.close()
        finally:
            proc.terminate()
            proc.wait(timeout=15)
print('Screenshots saved:', len(list(OUT.glob('*.png'))))
