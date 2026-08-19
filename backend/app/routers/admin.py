# backend/app/routers/admin.py

import os
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.scheduler import reschedule_daily_job
from app.core.time_utils import taiwan_now
from app.models.database_models import Alert, Article, Board, CrawlLog, User, WatchKeyword
from app.services.article_service import get_or_create_board, get_or_create_platform
from app.services.audit_service import list_recent_audits, record_audit
from app.services.auth_service import (
    hash_password,
    require_admin,
    serialize_user_admin,
)
from app.services.settings_service import get_all_settings, get_setting, update_settings


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
    action: str | None = Query(default=None, description="只看某一類操作，例如 create_user"),
    db: Session = Depends(get_db),
):
    """
    說明：
    列出最近的後台操作稽核紀錄，最新的排前面；可用 action 篩選類型。
    """

    return {
        "status": "success",
        "data": {
            "logs": list_recent_audits(db, limit=limit, action=action),
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


# ── 系統總覽 ────────────────────────────────────────────────

@router.get("/system-overview", dependencies=[Depends(require_admin)])
def system_overview(db: Session = Depends(get_db)):
    """
    說明：
    後台系統總覽：一次回傳資料庫、Gemini、文章、情緒覆蓋、爬取、
    排程、使用者與預警等營運指標，讓管理員一眼掌握全站狀態。
    """

    # 以下查詢若能成功，即代表資料庫連線正常。
    total_articles = db.query(func.count(Article.id)).scalar() or 0
    rated_articles = (
        db.query(func.count(Article.id)).filter(Article.sentiment.isnot(None)).scalar() or 0
    )

    # 各看板文章數
    board_counts = [
        {"board": name, "count": count}
        for name, count in (
            db.query(Board.name, func.count(Article.id))
            .outerjoin(Article, Article.board_id == Board.id)
            .group_by(Board.name)
            .order_by(desc(func.count(Article.id)))
            .all()
        )
    ]

    last_crawl = (
        db.query(CrawlLog)
        .order_by(desc(CrawlLog.started_at))
        .first()
    )

    return {
        "status": "success",
        "data": {
            "database": "connected",
            "gemini_configured": bool(os.getenv("GOOGLE_API_KEY")),
            "articles": {
                "total": total_articles,
                "rated": rated_articles,
                "rated_percent": round(rated_articles / total_articles * 100, 1) if total_articles else 0,
                "by_board": board_counts,
            },
            "last_crawl": {
                "status": last_crawl.status if last_crawl else None,
                "board": last_crawl.board.name if last_crawl and last_crawl.board else None,
                "time": last_crawl.started_at.isoformat() if last_crawl and last_crawl.started_at else None,
            },
            "scheduler": {
                "enabled": bool(get_setting(db, "auto_crawl_enabled")),
                "hour": get_setting(db, "auto_crawl_hour"),
                "pages": get_setting(db, "auto_crawl_pages"),
            },
            "users": _user_stats(db),
            "monitor": {
                "watch_keywords": db.query(func.count(WatchKeyword.id)).scalar() or 0,
                "unread_alerts": db.query(func.count(Alert.id)).filter(Alert.is_read == 0).scalar() or 0,
            },
        },
    }


# ── 系統設定 ────────────────────────────────────────────────

class SettingsRequest(BaseModel):
    alert_warning_negative: float | None = Field(default=None, ge=0, le=100)
    alert_critical_negative: float | None = Field(default=None, ge=0, le=100)
    alert_min_articles: int | None = Field(default=None, ge=1, le=1000)
    auto_crawl_enabled: bool | None = None
    auto_crawl_hour: int | None = Field(default=None, ge=0, le=23)
    auto_crawl_pages: int | None = Field(default=None, ge=1, le=20)
    dcard_crawl_enabled: bool | None = None
    mobile01_crawl_enabled: bool | None = None
    threads_crawl_enabled: bool | None = None


@router.get("/settings", dependencies=[Depends(require_admin)])
def read_settings(db: Session = Depends(get_db)):
    return {"status": "success", "data": get_all_settings(db)}


@router.put("/settings", dependencies=[Depends(require_admin)])
def write_settings(
    payload: SettingsRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    說明：
    更新系統設定（只更新有帶入的欄位）。若調整了排程時間，
    會即時重排每日任務。所有變更寫入稽核紀錄。
    """

    values = {k: v for k, v in payload.model_dump().items() if v is not None}

    if not values:
        raise HTTPException(status_code=400, detail="沒有要更新的設定。")

    updated = update_settings(db, values)

    # 若改了執行時間，即時套用到排程。
    if "auto_crawl_hour" in values:
        reschedule_daily_job(int(values["auto_crawl_hour"]))

    record_audit(
        db,
        actor=current_admin,
        action="update_settings",
        target_username=None,
        detail="更新了系統設定：" + "、".join(values.keys()),
    )
    db.commit()

    return {"status": "success", "data": updated}


# ── 看板管理 ────────────────────────────────────────────────

def _serialize_board(board, article_count: int) -> dict:
    return {
        "id": board.id,
        "name": board.name,
        "display_name": board.display_name or board.name,
        "platform": board.platform.name if board.platform else "ptt",
        "is_active": bool(board.is_active),
        "article_count": article_count,
    }


@router.get("/boards", dependencies=[Depends(require_admin)])
def list_boards(db: Session = Depends(get_db)):
    """列出所有看板，含文章數與啟用狀態。"""
    rows = (
        db.query(Board, func.count(Article.id))
        .outerjoin(Article, Article.board_id == Board.id)
        .group_by(Board.id)
        .order_by(desc(Board.is_active), Board.name)
        .all()
    )
    return {
        "status": "success",
        "data": {"boards": [_serialize_board(b, c) for b, c in rows]},
    }


class CreateBoardRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str | None = Field(default=None, max_length=100)
    # 平台：ptt（PTT 看板）、dcard（Dcard 論壇）或 mobile01（Mobile01 討論區）。
    platform: str = Field(default="ptt")


@router.post("/boards", dependencies=[Depends(require_admin)])
def create_board(
    payload: CreateBoardRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    name = payload.name.strip()
    platform_name = (payload.platform or "ptt").strip().lower()
    if platform_name not in ("ptt", "dcard", "mobile01", "threads"):
        raise HTTPException(status_code=400, detail="平台只能是 ptt、dcard、mobile01 或 threads。")

    platform = get_or_create_platform(db, platform_name)

    # 看板名稱在「同一平台內」唯一即可；不同平台可有同名看板（例如兩邊都有 facelift）。
    existing = (
        db.query(Board)
        .filter(Board.platform_id == platform.id, Board.name == name)
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="此看板已存在。")

    board = get_or_create_board(db, platform.id, name)
    board.display_name = (payload.display_name or "").strip() or name
    if platform_name == "dcard":
        board.url = f"https://www.dcard.tw/f/{name}"
    elif platform_name == "mobile01":
        board.url = f"https://www.mobile01.com/topiclist.php?f={name}"
    elif platform_name == "threads":
        board.url = f"https://www.threads.com/search?q={quote(name)}"
    else:
        board.url = f"https://www.ptt.cc/bbs/{name}/index.html"
    board.is_active = 1

    record_audit(db, actor=current_admin, action="create_board",
                 target_username=None,
                 detail=f"新增爬取看板「{name}」（{platform_name}）")
    db.commit()
    db.refresh(board)

    return {"status": "success", "board": _serialize_board(board, 0)}


class UpdateBoardRequest(BaseModel):
    is_active: bool | None = None
    display_name: str | None = Field(default=None, max_length=100)


@router.patch("/boards/{board_id}", dependencies=[Depends(require_admin)])
def update_board(
    board_id: int,
    payload: UpdateBoardRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    board = db.query(Board).filter(Board.id == board_id).first()
    if board is None:
        raise HTTPException(status_code=404, detail="找不到此看板。")

    changes = []
    if payload.is_active is not None:
        board.is_active = 1 if payload.is_active else 0
        changes.append("啟用爬取" if payload.is_active else "停用爬取")
    if payload.display_name is not None:
        board.display_name = payload.display_name.strip() or board.name
        changes.append("修改顯示名稱")

    if changes:
        record_audit(db, actor=current_admin, action="update_board",
                     target_username=None, detail=f"看板「{board.name}」：" + "、".join(changes))

    article_count = db.query(func.count(Article.id)).filter(Article.board_id == board.id).scalar() or 0
    db.commit()
    db.refresh(board)

    return {"status": "success", "board": _serialize_board(board, article_count)}


@router.delete("/boards/{board_id}", dependencies=[Depends(require_admin)])
def delete_board(
    board_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    board = db.query(Board).filter(Board.id == board_id).first()
    if board is None:
        raise HTTPException(status_code=404, detail="找不到此看板。")

    article_count = db.query(func.count(Article.id)).filter(Article.board_id == board.id).scalar() or 0
    if article_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"此看板已有 {article_count} 篇文章，無法刪除；可改為「停用」。",
        )

    name = board.name
    db.delete(board)
    record_audit(db, actor=current_admin, action="delete_board",
                 target_username=None, detail=f"刪除看板「{name}」")
    db.commit()

    return {"status": "success", "message": "看板已刪除。"}
