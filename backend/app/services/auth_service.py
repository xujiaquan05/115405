# backend/app/services/auth_service.py

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
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
PBKDF2_ITERATIONS = 260_000

_bearer_scheme = HTTPBearer(auto_error=False)


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


def create_access_token(user: User) -> str:
    """
    簽發 JWT access token，內容包含使用者 id、帳號與角色。
    """

    now = datetime.now(timezone.utc)

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
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登入已過期，請重新登入。")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="無效的登入憑證，請重新登入。")


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """
    以帳號密碼驗證使用者。
    帳號不存在、已停用或密碼錯誤都回傳 None，
    不透露是哪一項錯誤，避免帳號枚舉攻擊。
    """

    user = db.query(User).filter(User.username == username).first()

    if user is None or not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency：從 Authorization: Bearer <token> 取得目前使用者。
    需要登入的 endpoint 加上 Depends(get_current_user) 即可。
    """

    if credentials is None:
        raise HTTPException(status_code=401, detail="請先登入。")

    payload = decode_access_token(credentials.credentials)

    user = db.query(User).filter(User.id == payload.get("uid")).first()

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="帳號不存在或已停用。")

    return user


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "role": user.role,
    }
