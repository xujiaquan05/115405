# backend/app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import RateLimiter
from app.core.time_utils import taiwan_now, utc_now
from app.models.database_models import User
from app.services.audit_service import record_audit, record_security_event
from app.services.auth_service import (
    ACCESS_TOKEN_COOKIE,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    TOKEN_EXPIRE_HOURS,
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    serialize_user,
    verify_password,
)
from app.services.password_policy import validate_password

router = APIRouter(
    prefix="/api/auth",
    tags=["Auth"],
)

# 說明：
# 限制每個 IP 每分鐘最多 5 次登入嘗試，防止暴力破解密碼。
login_rate_limiter = RateLimiter(max_requests=5, window_seconds=60, scope="login")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


@router.post("/login", dependencies=[Depends(login_rate_limiter)])
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    說明：
    帳號密碼登入。token 會寫進 httpOnly cookie，JavaScript 讀不到，
    因此就算前端有 XSS 也偷不走登入憑證。

    回應中仍附上 access_token，供測試與外部 API 用戶端以
    Authorization: Bearer <token> 呼叫；瀏覽器端不需要（也不應）保存它。
    """

    username = payload.username.strip()
    result = authenticate_user(db, username, payload.password)

    if result.status == "locked":
        record_security_event(
            db, "login_locked", username,
            f"帳號鎖定中，仍嘗試登入（約 {result.retry_after_minutes} 分鐘後解鎖）",
        )
        raise HTTPException(
            status_code=423,
            detail=f"因連續登入失敗，帳號已暫時鎖定，請於約 {result.retry_after_minutes} 分鐘後再試。",
        )

    if result.status != "ok":
        # 訊息與「密碼錯誤」完全相同，不讓攻擊者判斷帳號是否存在。
        record_security_event(db, "login_failed", username, "登入失敗（帳號或密碼錯誤）")
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤，請重新輸入。")

    user = result.user

    # 記錄最後登入時間（台灣時間），供後台觀察帳號活躍度。
    user.last_login_at = taiwan_now()
    db.commit()

    token = create_access_token(user)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=token,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        max_age=TOKEN_EXPIRE_HOURS * 3600,
        path="/",
    )

    return {
        "status": "success",
        # 與 cookie 內是同一個 token，不要另外簽一個。
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@router.post("/logout")
def logout(response: Response):
    """
    說明：
    清除登入 cookie。

    因為 cookie 是 httpOnly，前端 JavaScript 無法自行刪除，
    一定要由伺服器回應 Set-Cookie 才能真正登出。
    不需要驗證身分：沒登入時呼叫也只是清一個不存在的 cookie。
    """

    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE,
        path="/",
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        httponly=True,
    )

    return {"status": "success", "message": "已登出。"}


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


class UpdateProfileRequest(BaseModel):
    # 三者皆選填：只更新有帶入的欄位。display_name 帶空字串會被 422 擋下；
    # avatar_emoji / avatar_color 帶空字串代表「清除」，改回顯示名稱首字 / 預設底色。
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    avatar_emoji: str | None = Field(default=None, max_length=16)
    avatar_color: str | None = Field(default=None, max_length=16)


@router.patch("/me")
def update_me(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    說明：
    使用者更新自己的顯示名稱與頭像（emoji / 底色）。其他敏感欄位（角色、
    啟用狀態）不開放自行修改，必須由管理員在帳號管理處調整。
    """

    if payload.display_name is not None:
        current_user.display_name = payload.display_name.strip()
    if payload.avatar_emoji is not None:
        current_user.avatar_emoji = payload.avatar_emoji.strip() or None
    if payload.avatar_color is not None:
        current_user.avatar_color = payload.avatar_color.strip() or None

    db.commit()
    db.refresh(current_user)

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

    validate_password(payload.new_password, current_user.username)

    current_user.password_hash = hash_password(payload.new_password)
    # 記錄變更時間，讓在此之前簽發的 token 全部失效（其他裝置會被登出）。
    current_user.password_changed_at = utc_now()

    record_audit(
        db,
        actor=current_user,
        action="change_password",
        target_username=current_user.username,
        detail="自行變更密碼（其他裝置的登入已失效）",
    )
    db.commit()

    return {
        "status": "success",
        "message": "密碼已更新，下次登入請使用新密碼。",
    }
