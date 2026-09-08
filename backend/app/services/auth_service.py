# backend/app/services/auth_service.py

import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.time_utils import taiwan_now
from app.models.database_models import User

load_dotenv()

logger = logging.getLogger(__name__)

# 說明：
# JWT_SECRET 用來簽發與驗證 token。
# 沒有設定時會產生隨機值並警告 —
# 開發時可以用，但每次重啟 server 所有 token 都會失效，
# 正式部署務必在環境變數設定固定的 JWT_SECRET。
JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    logger.warning(
        "JWT_SECRET is not set; using a random secret. "
        "All tokens will be invalidated on restart."
    )

JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "12"))

# 說明：
# 密碼雜湊使用 Python 標準函式庫的 PBKDF2-HMAC-SHA256，
# 不需額外安裝原生套件（如 bcrypt），部署到任何環境都能運作。
# OWASP 目前建議 PBKDF2-HMAC-SHA256 使用 600,000 次迭代。
# 迭代次數會寫進雜湊字串裡，所以舊密碼仍可驗證；使用者下次登入時會自動升級。
# 測試以環境變數調低，否則每次建立測試帳號都要多花數百毫秒。
PBKDF2_DEFAULT_ITERATIONS = 600_000
PBKDF2_ITERATIONS = int(os.getenv("PBKDF2_ITERATIONS", str(PBKDF2_DEFAULT_ITERATIONS)))

_bearer_scheme = HTTPBearer(auto_error=False)

# 說明：
# token 改放在 httpOnly cookie，JavaScript 讀不到，
# 這樣即使前端某處有 XSS，攻擊者也偷不走登入憑證
#（存在 localStorage 的話一行 JS 就拿走了）。
#
# 仍保留 Authorization header 的支援：測試與外部 API 用戶端沿用原本方式，
# 兩者擇一即可。
# 帳號層級的登入保護。
# 既有的 RateLimiter 只看 IP，攻擊者換 IP 就能繞過；
# 這裡改以「帳號」為單位計數並寫進資料庫，換 IP 或重啟服務都不會重置。
MAX_FAILED_LOGINS = int(os.getenv("MAX_FAILED_LOGINS", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "15"))

ACCESS_TOKEN_COOKIE = "access_token"

# SameSite=strict：跨站請求一律不帶這個 cookie，等於擋掉 CSRF。
# 本系統前端與 API 同源，全部靠 XHR 呼叫，因此不受影響。
COOKIE_SAMESITE = "strict"

# Secure cookie 只有 https 才會被瀏覽器接受。
# 開發時走 http://localhost，設了會讓 cookie 直接被丟棄而登不進去，
# 因此依 APP_ENV 判斷；正式部署務必讓 APP_ENV 不是 development。
COOKIE_SECURE = os.getenv("APP_ENV", "development").lower() != "development"


def _read_token(request: Request | None, credentials: HTTPAuthorizationCredentials | None) -> str | None:
    """優先讀 Authorization header，其次讀 cookie。

    header 是呼叫端「明確指定」的身分，cookie 則是瀏覽器自動附帶的；
    兩者同時存在時應以明確指定者為準，否則帶了 header 卻被瀏覽器殘留的
    cookie 蓋掉，會變成難以察覺的錯誤身分。
    """
    if credentials is not None:
        return credentials.credentials

    if request is not None:
        return request.cookies.get(ACCESS_TOKEN_COOKIE) or None

    return None


def hash_password(password: str) -> str:
    """
    產生密碼雜湊，格式：
    pbkdf2_sha256$迭代次數$salt(hex)$hash(hex)
    每個帳號都有獨立的隨機 salt。
    """

    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    )

    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """
    驗證密碼是否符合雜湊值。
    使用 hmac.compare_digest 做常數時間比較，避免 timing attack。
    """

    try:
        algorithm, iterations, salt, expected = password_hash.split("$")

        if algorithm != "pbkdf2_sha256":
            return False

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations),
        )

        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, AttributeError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """判斷雜湊是否用較舊（較弱）的迭代次數產生。

    提高迭代次數後不能強迫所有人改密碼，因此改成「下次登入時
    用明文重新雜湊一次」，逐步把舊帳號升級上來。
    """
    try:
        algorithm, iterations, _salt, _digest = password_hash.split("$")
    except (ValueError, AttributeError):
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    try:
        return int(iterations) < PBKDF2_ITERATIONS
    except ValueError:
        return False


def create_access_token(user: User) -> str:
    """
    簽發 JWT access token，內容包含使用者 id、帳號與角色。
    """

    now = datetime.now(UTC)

    payload = {
        "sub": user.username,
        "uid": user.id,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    驗證並解析 JWT。
    token 無效或過期時拋出 HTTPException 401。
    """

    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(status_code=401, detail="登入已過期，請重新登入。") from error
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail="無效的登入憑證，請重新登入。") from error


@dataclass
class LoginResult:
    """登入結果。

    status:
      ok      驗證通過
      invalid 帳號不存在 / 已停用 / 密碼錯誤（一律相同，避免帳號枚舉）
      locked  密碼正確，但帳號因連續失敗而暫時鎖定
    """

    status: str
    user: User | None = None
    retry_after_minutes: int = 0


def is_locked(user: User) -> bool:
    locked_until = getattr(user, "locked_until", None)
    return locked_until is not None and locked_until > taiwan_now()


def _register_failure(db: Session, user: User) -> None:
    """累計失敗次數，達門檻就鎖定一段時間。"""
    user.failed_login_count = (user.failed_login_count or 0) + 1

    if user.failed_login_count >= MAX_FAILED_LOGINS:
        user.locked_until = taiwan_now() + timedelta(minutes=LOCKOUT_MINUTES)
        user.failed_login_count = 0  # 鎖定後重新計數，解鎖再犯才會再次鎖

    db.commit()


def authenticate_user(db: Session, username: str, password: str) -> LoginResult:
    """
    以帳號密碼驗證使用者。

    帳號不存在、已停用或密碼錯誤一律回傳 invalid，不透露是哪一項，
    避免攻擊者用錯誤訊息判斷帳號是否存在。

    唯一的例外是「密碼正確但帳號被鎖定」才回報 locked：
    對方既然已經知道密碼，告知鎖定並不會多洩漏什麼，
    卻能讓真正的使用者明白為何登不進去。
    """

    user = db.query(User).filter(User.username == username).first()

    if user is None or not user.is_active:
        return LoginResult(status="invalid")

    password_ok = verify_password(password, user.password_hash)

    if is_locked(user):
        if password_ok:
            remaining = user.locked_until - taiwan_now()
            minutes = max(1, int(remaining.total_seconds() // 60) + 1)
            return LoginResult(status="locked", retry_after_minutes=minutes)

        return LoginResult(status="invalid")

    if not password_ok:
        _register_failure(db, user)
        return LoginResult(status="invalid")

    # 登入成功：清掉失敗計數與鎖定狀態。
    if user.failed_login_count or user.locked_until:
        user.failed_login_count = 0
        user.locked_until = None

    # 密碼正確時順手把舊雜湊升級到目前的迭代次數（使用者無感）。
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    db.commit()

    return LoginResult(status="ok", user=user)


def token_issued_before_password_change(payload: dict, user: User) -> bool:
    """token 是否在使用者變更密碼之前簽發。

    沒有這個檢查，改密碼並不會把已經登入的攻擊者踢下線 ——
    他手上的 token 仍可用到過期為止，而那正是最需要擋住的時候。
    """
    changed_at = getattr(user, "password_changed_at", None)

    if changed_at is None:
        return False

    issued_at = payload.get("iat")

    if issued_at is None:
        return False

    # iat 是 UTC 時戳；password_changed_at 也以 UTC 儲存（見 time_utils.utc_now）。
    if isinstance(issued_at, datetime):
        issued_dt = issued_at.replace(tzinfo=None)
    else:
        issued_dt = datetime.fromtimestamp(int(issued_at), tz=UTC).replace(tzinfo=None)

    # 不要把 changed_at 也截到整秒：iat 本身已經是整秒，
    # 兩邊都截秒的話，同一秒內簽發的 token 會比對成「不早於」而擋不掉。
    # 保留微秒讓「該秒稍早簽發的 token」確實小於變更時間。
    #
    # 代價是：若使用者在改密碼的同一秒內重新登入，新 token 也會被判失效，
    # 需要再登入一次。這個方向是安全的（寧可多登一次，不可放行舊 token）。
    return issued_dt < changed_at


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency：從 Authorization: Bearer <token> 取得目前使用者。
    需要登入的 endpoint 加上 Depends(get_current_user) 即可。
    """

    token = _read_token(request, credentials)

    if token is None:
        raise HTTPException(status_code=401, detail="請先登入。")

    payload = decode_access_token(token)

    user = db.query(User).filter(User.id == payload.get("uid")).first()

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="帳號不存在或已停用。")

    if token_issued_before_password_change(payload, user):
        raise HTTPException(status_code=401, detail="密碼已變更，請重新登入。")

    return user


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """FastAPI dependency：有帶有效 token 就回傳使用者，否則回傳 None。

    用於「訪客也能看、但登入後看到的是自己的資料」的端點，
    例如預警清單：未登入時回傳空清單而不是 401。
    憑證無效時一律當作訪客，不拋錯。
    """

    token = _read_token(request, credentials)

    if token is None:
        return None

    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None

    user = db.query(User).filter(User.id == payload.get("uid")).first()

    if user is None or not user.is_active:
        return None

    if token_issued_before_password_change(payload, user):
        return None

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency：只允許 admin 角色使用。
    非管理員一律回 403。用於後台管理相關 endpoint。
    """

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理員權限。")

    return current_user


# 系統初始化時使用的預設密碼。部署後必須更換，
# 因此提供一個檢查函式，讓後台能主動提醒尚未更換的帳號。
DEFAULT_ADMIN_PASSWORD = "admin123"


def uses_default_password(user: User) -> bool:
    """判斷帳號是否仍在使用預設密碼（admin123）。"""
    try:
        return verify_password(DEFAULT_ADMIN_PASSWORD, user.password_hash)
    except Exception:
        return False


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "role": user.role,
        "is_active": bool(user.is_active),
        "avatar_emoji": user.avatar_emoji,
        "avatar_color": user.avatar_color,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def serialize_user_admin(user: User) -> dict:
    """
    給後台使用者列表用的完整資訊，
    比 serialize_user 多了啟用狀態與建立時間。
    """

    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "role": user.role,
        "is_active": bool(user.is_active),
        "avatar_emoji": user.avatar_emoji,
        "avatar_color": user.avatar_color,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
