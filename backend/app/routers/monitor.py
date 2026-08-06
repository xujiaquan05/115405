# backend/app/routers/monitor.py

import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.scheduler import run_daily_job
from app.models.database_models import Alert, WatchKeyword
from app.services.alert_service import (
    run_alert_checks,
    serialize_alert,
    serialize_watch_keyword,
)
from app.services.audit_service import record_audit
from app.services.auth_service import get_current_user, require_admin


router = APIRouter(
    prefix="/api/monitor",
    tags=["Monitor"],
)


# ── 監控關鍵字 ──────────────────────────────────────────────

class WatchKeywordRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=255)
    days: int = Field(default=7, ge=1, le=180)


@router.get("/keywords")
def list_keywords(db: Session = Depends(get_db)):
    watches = db.query(WatchKeyword).order_by(desc(WatchKeyword.created_at)).all()
    return {
        "status": "success",
        "data": {"keywords": [serialize_watch_keyword(w) for w in watches]},
    }


@router.post("/keywords", dependencies=[Depends(get_current_user)])
def add_keyword(
    payload: WatchKeywordRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    keyword = payload.keyword.strip()

    existing = db.query(WatchKeyword).filter(WatchKeyword.keyword == keyword).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="此關鍵字已在監控清單中。")

    watch = WatchKeyword(keyword=keyword, days=payload.days, enabled=1)
    db.add(watch)
    record_audit(db, actor=current_user, action="add_watch_keyword",
                 target_username=None, detail=f"新增監控關鍵字「{keyword}」")
    db.commit()
    db.refresh(watch)

    return {"status": "success", "keyword": serialize_watch_keyword(watch)}


class UpdateKeywordRequest(BaseModel):
    enabled: bool | None = None
    days: int | None = Field(default=None, ge=1, le=180)


@router.patch("/keywords/{keyword_id}", dependencies=[Depends(get_current_user)])
def update_keyword(
    keyword_id: int,
    payload: UpdateKeywordRequest,
    db: Session = Depends(get_db),
):
    watch = db.query(WatchKeyword).filter(WatchKeyword.id == keyword_id).first()
    if watch is None:
        raise HTTPException(status_code=404, detail="找不到此監控關鍵字。")

    if payload.enabled is not None:
        watch.enabled = 1 if payload.enabled else 0
    if payload.days is not None:
        watch.days = payload.days

    db.commit()
    db.refresh(watch)

    return {"status": "success", "keyword": serialize_watch_keyword(watch)}


@router.delete("/keywords/{keyword_id}", dependencies=[Depends(get_current_user)])
def delete_keyword(
    keyword_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    watch = db.query(WatchKeyword).filter(WatchKeyword.id == keyword_id).first()
    if watch is None:
        raise HTTPException(status_code=404, detail="找不到此監控關鍵字。")

    name = watch.keyword
    db.delete(watch)
    record_audit(db, actor=current_user, action="delete_watch_keyword",
                 target_username=None, detail=f"移除監控關鍵字「{name}」")
    db.commit()

    return {"status": "success", "message": "已移除監控關鍵字。"}


# ── 預警 ────────────────────────────────────────────────────

@router.get("/alerts")
def list_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    alerts = db.query(Alert).order_by(desc(Alert.created_at), desc(Alert.id)).limit(limit).all()
    unread = db.query(func.count(Alert.id)).filter(Alert.is_read == 0).scalar() or 0

    return {
        "status": "success",
        "data": {
            "alerts": [serialize_alert(a) for a in alerts],
            "unread_count": unread,
        },
    }


@router.post("/alerts/check", dependencies=[Depends(get_current_user)])
def check_alerts_now(db: Session = Depends(get_db)):
    """
    說明：
    立即對所有監控關鍵字執行風險評估（不爬新資料），
    達門檻就建立預警。適合示範與即時檢查。
    """

    created = run_alert_checks(db)
    return {
        "status": "success",
        "created_count": len(created),
        "alerts": [serialize_alert(a) for a in created],
    }


@router.post("/alerts/{alert_id}/read", dependencies=[Depends(get_current_user)])
def mark_alert_read(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert is None:
        raise HTTPException(status_code=404, detail="找不到此預警。")

    alert.is_read = 1
    db.commit()

    return {"status": "success"}


@router.post("/alerts/read-all", dependencies=[Depends(get_current_user)])
def mark_all_alerts_read(db: Session = Depends(get_db)):
    db.query(Alert).filter(Alert.is_read == 0).update({Alert.is_read: 1})
    db.commit()

    return {"status": "success"}


# ── 手動執行每日任務（示範用） ──────────────────────────────

@router.post("/run-now", dependencies=[Depends(require_admin)])
def run_daily_now():
    """
    說明：
    手動觸發完整每日任務（爬取 → 評分 → 預警）在背景執行，
    讓 demo 不必等到排程時間。僅管理員可用。
    """

    threading.Thread(target=lambda: run_daily_job(force=True), daemon=True).start()

    return {
        "status": "success",
        "message": "每日任務已在背景開始執行（爬取 → 情緒評分 → 風險預警）。",
    }
