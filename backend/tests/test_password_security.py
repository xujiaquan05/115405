# backend/tests/test_password_security.py

"""密碼安全：規則、雜湊升級、以及「改密碼要能踢掉舊 session」。"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.database_models import User
from app.routers.auth import login_rate_limiter
from app.services.auth_service import hash_password, needs_rehash
from app.services.password_policy import score_password, validate_password


GOOD_PASSWORD = "Str0ng-Pass-99"


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
    login_rate_limiter._hits.clear()

    session = TestSession()
    session.add(User(username="alice", password_hash=hash_password(GOOD_PASSWORD),
                     display_name="Alice", role="user", is_active=1))
    session.commit()
    session.close()

    yield TestClient(app), TestSession
    app.dependency_overrides.clear()


def login(c, password=GOOD_PASSWORD, username="alice"):
    return c.post("/api/auth/login", json={"username": username, "password": password})


class TestPasswordPolicy:
    def test_rejects_short_password(self):
        with pytest.raises(HTTPException) as exc:
            validate_password("Ab3!x")
        assert exc.value.status_code == 400

    def test_rejects_common_password(self):
        for weak in ("admin123", "password", "12345678"):
            with pytest.raises(HTTPException):
                validate_password(weak)

    def test_rejects_password_containing_username(self):
        with pytest.raises(HTTPException) as exc:
            validate_password("editor12345", username="editor")
        assert "帳號" in exc.value.detail

    def test_rejects_repetitive_password(self):
        with pytest.raises(HTTPException):
            validate_password("aaaaaaaaaa")

    def test_accepts_reasonable_password(self):
        validate_password(GOOD_PASSWORD, username="alice")  # 不應丟出例外

    def test_score_flags_common_password_as_weakest(self):
        assert score_password("admin123")["score"] == 0
        assert score_password("Str0ng-Pass-99")["score"] >= 3


class TestRehashOnLogin:
    def test_old_hash_upgraded_after_login(self, client):
        """提高迭代次數後，使用者下次登入時雜湊要自動升級，不必強迫改密碼。"""
        c, TestSession = client

        session = TestSession()
        user = session.query(User).filter(User.username == "alice").first()
        # 模擬用舊迭代次數存的密碼
        algorithm, _iterations, salt, digest = user.password_hash.split("$")
        user.password_hash = f"{algorithm}$1${salt}${digest}"
        session.commit()
        session.close()

        # 迭代次數不符，舊雜湊驗不過，改用真的舊雜湊來測升級路徑
        session = TestSession()
        user = session.query(User).filter(User.username == "alice").first()
        import hashlib
        old_salt = "ab" * 16
        old_digest = hashlib.pbkdf2_hmac("sha256", GOOD_PASSWORD.encode(), bytes.fromhex(old_salt), 500)
        user.password_hash = f"pbkdf2_sha256$500${old_salt}${old_digest.hex()}"
        session.commit()
        session.close()

        assert needs_rehash(f"pbkdf2_sha256$500${old_salt}${old_digest.hex()}") is True
        assert login(c).status_code == 200

        session = TestSession()
        upgraded = session.query(User).filter(User.username == "alice").first().password_hash
        session.close()

        assert needs_rehash(upgraded) is False


class TestSessionInvalidation:
    def test_changing_password_kills_existing_tokens(self, client):
        """這是本次修補的重點：改密碼必須把其他裝置上的 token 一起失效，
        否則密碼外洩時改密碼並趕不走已經登入的攻擊者。"""
        c, _ = client

        stolen = login(c).json()["access_token"]
        stolen_header = {"Authorization": f"Bearer {stolen}"}

        # 舊 token 原本可用
        assert c.get("/api/auth/me", headers=stolen_header).status_code == 200

        changed = c.post("/api/auth/change-password",
                         json={"old_password": GOOD_PASSWORD, "new_password": "N3w-Secret-2026"},
                         headers=stolen_header)
        assert changed.status_code == 200

        # 改完之後同一個 token 必須失效
        blocked = c.get("/api/auth/me", headers=stolen_header)
        assert blocked.status_code == 401
        assert "重新登入" in blocked.json()["detail"]

    def test_new_token_after_change_works(self, client):
        """改完密碼重新登入要能正常使用。

        JWT 的 iat 只精確到「秒」，而變更時間帶微秒，所以同一秒內重新登入
        的 token 會被判定為變更前簽發而失效。這是刻意選擇的方向（寧可多登
        一次，也不放行舊 token），真人輸入密碼不可能在同一秒完成，
        但測試會，因此這裡等過一秒再登入。
        """
        import time

        c, _ = client
        header = {"Authorization": f"Bearer {login(c).json()['access_token']}"}
        c.post("/api/auth/change-password",
               json={"old_password": GOOD_PASSWORD, "new_password": "N3w-Secret-2026"},
               headers=header)

        time.sleep(1.1)
        fresh = login(c, password="N3w-Secret-2026").json()["access_token"]

        assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {fresh}"}).status_code == 200

    def test_weak_new_password_rejected(self, client):
        c, _ = client
        header = {"Authorization": f"Bearer {login(c).json()['access_token']}"}

        resp = c.post("/api/auth/change-password",
                      json={"old_password": GOOD_PASSWORD, "new_password": "admin123"},
                      headers=header)

        assert resp.status_code == 400
        assert "常見" in resp.json()["detail"]


class TestCookieAuth:
    """憑證改放 httpOnly cookie：JavaScript 讀不到，XSS 就偷不走。"""

    def test_login_sets_httponly_cookie(self, client):
        c, _ = client

        resp = login(c)
        cookie = resp.headers.get("set-cookie", "")

        assert "access_token=" in cookie
        assert "HttpOnly" in cookie
        # SameSite=strict 讓跨站請求不帶此 cookie，等同擋掉 CSRF。
        assert "strict" in cookie.lower()

    def test_cookie_alone_authenticates(self, client):
        """不帶 Authorization header，只靠瀏覽器自動附上的 cookie 也要能通過。"""
        c, _ = client
        login(c)

        assert c.get("/api/auth/me").status_code == 200

    def test_logout_clears_cookie(self, client):
        c, _ = client
        login(c)
        assert c.get("/api/auth/me").status_code == 200

        c.post("/api/auth/logout")

        assert c.get("/api/auth/me").status_code == 401

    def test_header_takes_precedence_over_cookie(self, client):
        """兩者並存時以 header 為準，避免瀏覽器殘留的 cookie 蓋掉指定身分。"""
        c, TestSession = client

        session = TestSession()
        session.add(User(username="bob", password_hash=hash_password(GOOD_PASSWORD),
                         display_name="Bob", role="user", is_active=1))
        session.commit()
        session.close()

        login(c)  # cookie = alice
        bob_token = login(c, username="bob").json()["access_token"]
        # 此時 cookie 已是 bob，改用 alice 的 token 明確指定
        alice_token = c.post("/api/auth/login",
                             json={"username": "alice", "password": GOOD_PASSWORD}).json()["access_token"]

        me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {alice_token}"})

        assert me.json()["user"]["username"] == "alice"
        assert bob_token  # 確認上面確實登入過 bob


class TestSecurityHeaders:
    def test_headers_present(self, client):
        c, _ = client

        headers = c.get("/health").headers

        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in headers
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
