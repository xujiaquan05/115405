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


def serialize_audit(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "actor_username": log.actor_username,
        "action": log.action,
        "target_username": log.target_username,
        "detail": log.detail,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


def list_recent_audits(db: Session, limit: int = 50) -> list[dict]:
    logs = (
        db.query(AuditLog)
        .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .limit(limit)
        .all()
    )

    return [serialize_audit(log) for log in logs]
