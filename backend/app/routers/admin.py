# backend/app/routers/admin.py

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.time_utils import taiwan_now
from app.models.database_models import User
from app.services.audit_service import list_recent_audits, record_audit
from app.services.auth_service import (
    hash_password,
    require_admin,
    serialize_user_admin,
)


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
)

VALID_ROLES = {"admin", "user"}


def _user_stats(db: Session) -> dict:
    # 說明：後台總覽卡片用的統計數字。
    total = db.query(func.count(User.id)).scalar() or 0
    admins = db.query(func.count(User.id)).filter(User.role == "admin").scalar() or 0
    active = db.query(func.count(User.id)).filter(User.is_active == 1).scalar() or 0

    week_ago = taiwan_now() - timedelta(days=7)
    logged_this_week = (
        db.query(func.count(User.id))
        .filter(User.last_login_at.isnot(None))
        .filter(User.last_login_at >= week_ago)
        .scalar()
        or 0
    )

    return {
        "total": total,
        "admins": admins,
        "active": active,
        "logged_this_week": logged_this_week,
    }


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=6, max_length=200)
    display_name: str | None = Field(default=None, max_length=100)
    role: str = Field(default="user")


class UpdateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    role: str | None = None
    is_active: bool | None = None
    new_password: str | None = Field(default=None, min_length=6, max_length=200)


@router.get("/users", dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)):
    """
    說明：
    列出所有使用者（後台管理用），新建立的排前面。
    """

    users = db.query(User).order_by(desc(User.created_at), desc(User.id)).all()

    return {
        "status": "success",
        "data": {
            "users": [serialize_user_admin(user) for user in users],
            "stats": _user_stats(db),
        },
    }


@router.get("/audit-logs", dependencies=[Depends(require_admin)])
def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    說明：
    列出最近的後台操作稽核紀錄，最新的排前面。
    """

    return {
        "status": "success",
        "data": {
            "logs": list_recent_audits(db, limit=limit),
        },
    }


@router.post("/users", dependencies=[Depends(require_admin)])
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    說明：
    管理員建立新帳號。帳號名稱不可重複，角色只能是 admin 或 user。
    """

    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="角色只能是 admin 或 user。")

    username = payload.username.strip()

    existing = db.query(User).filter(User.username == username).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="此帳號名稱已存在。")

    role_label = "管理員" if payload.role == "admin" else "一般使用者"

    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        display_name=(payload.display_name or "").strip() or username,
        role=payload.role,
        is_active=1,
    )

    db.add(user)
    record_audit(
        db,
        actor=current_admin,
        action="create_user",
        target_username=username,
        detail=f"建立了帳號「{username}」（{role_label}）",
    )
    db.commit()
    db.refresh(user)

    return {
        "status": "success",
        "user": serialize_user_admin(user),
    }


@router.patch("/users/{user_id}", dependencies=[Depends(require_admin)])
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    說明：
    更新使用者：顯示名稱、角色、啟用狀態，或由管理員重設密碼。

    為避免把自己鎖在系統外，管理員不能對「自己」降權或停用；
    其餘帳號（包含其他管理員）皆可調整。
    """

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="找不到此使用者。")

    is_self = user.id == current_admin.id
    changes: list[str] = []

    if payload.role is not None and payload.role != user.role:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="角色只能是 admin 或 user。")
        if is_self and payload.role != "admin":
            raise HTTPException(status_code=400, detail="不能取消自己的管理員權限。")
        user.role = payload.role
        changes.append(f"角色改為{'管理員' if payload.role == 'admin' else '一般使用者'}")

    if payload.is_active is not None and bool(payload.is_active) != bool(user.is_active):
        if is_self and payload.is_active is False:
            raise HTTPException(status_code=400, detail="不能停用自己的帳號。")
        user.is_active = 1 if payload.is_active else 0
        changes.append("啟用帳號" if payload.is_active else "停用帳號")

    if payload.display_name is not None:
        user.display_name = payload.display_name.strip() or user.username
        changes.append("修改顯示名稱")

    if payload.new_password is not None:
        user.password_hash = hash_password(payload.new_password)
        changes.append("重設密碼")

    if changes:
        record_audit(
            db,
            actor=current_admin,
            action="update_user",
            target_username=user.username,
            detail=f"對「{user.username}」{ '、'.join(changes) }",
        )

    db.commit()
    db.refresh(user)

    return {
        "status": "success",
        "user": serialize_user_admin(user),
    }


@router.delete("/users/{user_id}", dependencies=[Depends(require_admin)])
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    說明：
    刪除使用者。管理員不能刪除自己，避免不小心把自己刪掉導致無人可管理。
    """

    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="不能刪除自己的帳號。")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="找不到此使用者。")

    deleted_username = user.username

    db.delete(user)
    record_audit(
        db,
        actor=current_admin,
        action="delete_user",
        target_username=deleted_username,
        detail=f"刪除了帳號「{deleted_username}」",
    )
    db.commit()

    return {
        "status": "success",
        "message": "使用者已刪除。",
    }
