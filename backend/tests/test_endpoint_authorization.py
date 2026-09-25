# backend/tests/test_endpoint_authorization.py

"""哪些端點可以不登入就呼叫，由這裡明確列出。

為什麼要這樣寫？
權限是一個一個端點掛上去的，漏掉一個不會有任何徵兆——
服務照跑、測試照過，只是那個端點對全世界開著。
實測就發生過兩次：四個爬取端點原本只要登入就能觸發（任何帳號都能替全站
燒掉 Gemini 額度），而 /api/crawler/status 把原始例外字串公開給未登入者。

因此改成「白名單」：公開端點必須寫在下面這份清單裡，
新增端點若忘了掛權限，這個測試就會失敗並指名是哪一個。
"""

from fastapi.routing import APIRoute, APIWebSocketRoute

from app.main import app

# 認得的權限相依函式名稱。
AUTH_DEPENDENCIES = {"get_current_user", "require_admin", "get_optional_user"}

# 刻意公開的端點，以及公開的理由。
PUBLIC_ENDPOINTS = {
    ("POST", "/api/auth/login"): "登入本身不能要求先登入",
    ("POST", "/api/auth/logout"): "清除 Cookie，未登入呼叫也無害",
    ("GET", "/api/dashboard/full"): "訪客瀏覽 Dashboard 是產品功能",
    ("GET", "/api/dashboard/boards"): "同上，儀表板的篩選選項",
    ("GET", "/api/articles/{article_id}"): "文章內容本來就是公開論壇的公開貼文",
    ("WEBSOCKET", "/ws/dashboard"): "推播爬取進度，不含帳號資料",
}


def _auth_dependencies(dependant) -> set[str]:
    """遞迴收集這個端點用到的權限相依函式名稱。"""
    found = set()

    if getattr(dependant, "call", None) is not None:
        name = getattr(dependant.call, "__name__", "")
        if name in AUTH_DEPENDENCIES:
            found.add(name)

    for sub in getattr(dependant, "dependencies", []):
        found |= _auth_dependencies(sub)

    return found


def _all_endpoints():
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                yield method, route.path, _auth_dependencies(route.dependant)
        elif isinstance(route, APIWebSocketRoute):
            yield "WEBSOCKET", route.path, _auth_dependencies(route.dependant)


class TestPublicSurface:
    def test_no_unexpected_public_endpoint(self):
        unguarded = {
            (method, path)
            for method, path, guards in _all_endpoints()
            if not guards and path.startswith(("/api", "/ws"))
        }

        unexpected = unguarded - set(PUBLIC_ENDPOINTS)

        assert not unexpected, (
            f"這些端點沒有任何權限限制：{sorted(unexpected)}。"
            "請掛上 get_current_user 或 require_admin；"
            "若確實要公開，請加進 PUBLIC_ENDPOINTS 並寫明理由。"
        )

    def test_the_public_list_has_no_stale_entries(self):
        # 清單留著已經受保護（或已刪除）的端點，會讓下一個人以為它還是公開的。
        unguarded = {
            (method, path)
            for method, path, guards in _all_endpoints()
            if not guards and path.startswith(("/api", "/ws"))
        }

        stale = set(PUBLIC_ENDPOINTS) - unguarded

        assert not stale, f"PUBLIC_ENDPOINTS 裡這些已經不是公開端點了：{sorted(stale)}"


class TestSensitiveOperationsRequireAdmin:
    """觸發爬取、管理帳號與系統設定都會影響全站，一般使用者不該碰得到。"""

    def _guards_for(self, method: str, path: str) -> set[str]:
        for route_method, route_path, guards in _all_endpoints():
            if (route_method, route_path) == (method, path):
                return guards

        raise AssertionError(f"找不到端點 {method} {path}，路徑可能改過了")

    def test_crawl_triggers_are_admin_only(self):
        for platform in ("ptt", "dcard", "mobile01", "threads"):
            assert "require_admin" in self._guards_for("POST", f"/api/crawler/{platform}")

    def test_crawl_reset_is_admin_only(self):
        assert "require_admin" in self._guards_for("POST", "/api/crawler/reset")

    def test_internal_status_is_admin_only(self):
        # 這兩個回應含有原始例外字串與系統處理進度。
        assert "require_admin" in self._guards_for("GET", "/api/crawler/status")
        assert "require_admin" in self._guards_for("GET", "/api/analysis/sentiment/status")

    def test_running_the_daily_job_is_admin_only(self):
        assert "require_admin" in self._guards_for("POST", "/api/monitor/run-now")

    def test_user_management_is_admin_only(self):
        assert "require_admin" in self._guards_for("GET", "/api/admin/users")
        assert "require_admin" in self._guards_for("POST", "/api/admin/users")
        assert "require_admin" in self._guards_for("DELETE", "/api/admin/users/{user_id}")

    def test_system_settings_are_admin_only(self):
        assert "require_admin" in self._guards_for("GET", "/api/admin/settings")
        assert "require_admin" in self._guards_for("PUT", "/api/admin/settings")
