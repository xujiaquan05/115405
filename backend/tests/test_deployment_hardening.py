# backend/tests/test_deployment_hardening.py

"""部署面的防護。

這些問題的共通點是「程式碼正確，但部署設定沒跟上」——
在開發機一切正常，上線後才默默失效，是最難察覺的一類缺陷。
"""

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def render_env() -> dict:
    config = yaml.safe_load((REPO_ROOT / "render.yaml").read_text(encoding="utf-8"))
    web = next(s for s in config["services"] if s["name"] == "medical-beauty-opinion")
    return {var["key"]: var for var in web["envVars"]}


class TestRenderConfig:
    def test_app_env_is_production(self):
        """APP_ENV 決定 cookie 要不要加 Secure、要不要送 HSTS。
        沒設定會被當成 development，等於把上線後的兩項防護關掉。"""
        env = render_env()

        assert env["APP_ENV"]["value"] == "production"

    def test_browser_crawlers_disabled_in_cloud(self):
        """Render 的容器沒有 Chromium，開著只會讓每日排程天天失敗。"""
        env = render_env()

        for key in ("DCARD_CRAWL_ENABLED", "MOBILE01_CRAWL_ENABLED", "THREADS_CRAWL_ENABLED"):
            assert env[key]["value"] == "false"

    def test_jwt_secret_is_generated_not_blank(self):
        env = render_env()

        assert env["JWT_SECRET"].get("generateValue") is True


class TestDockerfile:
    def test_runs_migrations_before_serving(self):
        """沒有這一步，Alembic 只在開發機有用，正式環境結構永遠不會更新。"""
        dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

        assert "alembic upgrade head" in dockerfile
        # 用 && 串接，migration 失敗就不該把服務跑起來。
        assert "alembic upgrade head &&" in dockerfile


class TestHealthEndpoint:
    def test_reports_ok_when_database_reachable(self, client):
        body = client.get("/health").json()

        assert body["api"] == "ok"
        assert body["database"] == "ok"

    def test_does_not_leak_connection_details_on_failure(self, client):
        """/health 不需登入即可存取，資料庫錯誤訊息會帶出主機位址與連接埠。

        錯誤必須發生在「執行查詢」時而不是取得 session 時：
        dependency 階段就拋錯的話，health_check 的 try/except 根本還沒開始，
        會直接落到全域錯誤處理，測不到這裡要驗的那段。
        """

        class BrokenSession:
            def execute(self, *args, **kwargs):
                raise RuntimeError('connection to server at "10.0.0.7", port 7042 failed')

        def broken_db():
            yield BrokenSession()

        app.dependency_overrides[get_db] = broken_db
        body = client.get("/health").json()

        assert body["database"] == "error"
        serialized = str(body)
        assert "10.0.0.7" not in serialized
        assert "7042" not in serialized


class TestUnhandledErrors:
    def test_returns_incident_id_without_exposing_the_exception(self, client):
        """未預期的錯誤要能被追查，但回應不可帶出內部細節。

        不能在測試中臨時新增路由來觸發錯誤：SPA 的 catch-all 路由已經註冊在前，
        後加的路由永遠不會被匹配到，收到的會是前端 HTML。
        改成讓既有 API 的 dependency 拋錯。
        """

        def broken_db():
            raise RuntimeError("secret internal detail")

        app.dependency_overrides[get_db] = broken_db

        resp = client.get("/api/dashboard/boards")
        body = resp.json()

        assert resp.status_code == 500
        assert len(body["incident_id"]) == 8
        assert body["incident_id"] in body["detail"]
        assert "secret internal detail" not in str(body)
