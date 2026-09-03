# backend/app/services/audit_service.py

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.time_utils import taiwan_now
from app.models.database_models import AuditLog, User


def record_audit(
    db: Session,
    actor: User,
    action: str,
    target_username: str | None,
    detail: str,
) -> None:
    """
    說明：
    寫入一筆後台操作稽核紀錄。
    呼叫端負責 commit（通常和主要動作在同一個 transaction 一起 commit）。
    """

    db.add(AuditLog(
        actor_id=actor.id,
        actor_username=actor.username,
        action=action,
        target_username=target_username,
        detail=detail,
        created_at=taiwan_now(),
    ))


def record_security_event(
    db: Session,
    action: str,
    username: str,
    detail: str,
) -> None:
    """記錄與帳號安全有關的事件（登入失敗、帳號鎖定等）。

    這類事件發生時「還沒有通過驗證的使用者」，所以不能用 record_audit
    （它需要一個 actor 物件）。actor_id 留空，actor_username 存嘗試登入的帳號名稱，
    帳號不存在時也照樣記錄——那本身就是值得追查的訊號。
    """

    db.add(AuditLog(
        actor_id=None,
        actor_username=username[:100] or "(unknown)",
        action=action,
        target_username=None,
        detail=detail,
        created_at=taiwan_now(),
    ))
    db.commit()


def serialize_audit(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "actor_username": log.actor_username,
        "action": log.action,
        "target_username": log.target_username,
        "detail": log.detail,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


def list_recent_audits(db: Session, limit: int = 50, action: str | None = None) -> list[dict]:
    query = db.query(AuditLog)

    if action:
        query = query.filter(AuditLog.action == action)

    logs = (
        query
        .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .limit(limit)
        .all()
    )

    return [serialize_audit(log) for log in logs]
