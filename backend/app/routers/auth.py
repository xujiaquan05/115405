# backend/app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import RateLimiter
from app.core.time_utils import taiwan_now
from app.models.database_models import User
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    serialize_user,
    verify_password,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Auth"],
)

# 說明：
# 限制每個 IP 每分鐘最多 5 次登入嘗試，防止暴力破解密碼。
login_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


@router.post("/login", dependencies=[Depends(login_rate_limiter)])
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    說明：
    帳號密碼登入，成功回傳 JWT access token 與使用者資訊。
    前端把 token 放進 Authorization: Bearer <token> 使用。
    """

    user = authenticate_user(db, payload.username.strip(), payload.password)

    if user is None:
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤，請重新輸入。")

    # 記錄最後登入時間（台灣時間），供後台觀察帳號活躍度。
    user.last_login_at = taiwan_now()
    db.commit()

    return {
        "status": "success",
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """
    說明：
    回傳目前登入者的資訊，前端可用來驗證 token 是否仍有效。
    """

    return {
        "status": "success",
        "user": serialize_user(current_user),
    }


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=6, max_length=200)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    說明：
    已登入使用者修改自己的密碼。
    必須先驗證舊密碼，避免 token 被盜用時密碼被直接改走。
    """

    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="舊密碼錯誤，請重新輸入。")

    if payload.old_password == payload.new_password:
        raise HTTPException(status_code=400, detail="新密碼不可與舊密碼相同。")

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()

    return {
        "status": "success",
        "message": "密碼已更新，下次登入請使用新密碼。",
    }
