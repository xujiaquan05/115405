# backend/app/routers/qa.py

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import RateLimiter
from app.core.time_utils import taiwan_now
from app.models.database_models import QAConversation
from app.services import plan_service
from app.services.auth_service import get_current_user
from app.services.rag_service import answer_question

router = APIRouter(
    prefix="/api/qa",
    tags=["AI Q&A"],
)

# 說明：
# 每個問題會消耗 1-2 次 Gemini 呼叫（花費 API key 額度），
# 因此限制每個 IP 每分鐘 10 個問題，
# 避免 public URL 被灌爆。
qa_rate_limiter = RateLimiter(max_requests=10, window_seconds=60, scope="qa")


class HistoryItem(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(default="", max_length=2000)


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)
    dashboard_context: dict[str, Any] | None = None
    # 最近幾輪對話（供 AI 理解接續型問題）。前端只需傳最後數則。
    history: list[HistoryItem] | None = None
    # 重新生成時帶 True：略過快取，強制重新呼叫 Gemini。
    no_cache: bool = False


@router.post("/ask", dependencies=[Depends(qa_rate_limiter)])
def ask_question(
    payload: QuestionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 額度先檢查再呼叫 LLM，避免用掉 API 額度後才擋下來。
    plan_service.ensure_qa_quota(db, current_user)

    history = [item.model_dump() for item in payload.history] if payload.history else None

    # 檢索期間不得超過方案的查詢天數上限（例如專業版 90 天）。
    max_days = plan_service.clamp_history_days(db, current_user, 365)
    dashboard_context = payload.dashboard_context
    if dashboard_context and isinstance(dashboard_context.get("days"), int):
        dashboard_context = {**dashboard_context, "days": min(dashboard_context["days"], max_days)}

    result = answer_question(
        db=db,
        question=payload.question.strip(),
        dashboard_context=dashboard_context,
        history=history,
        use_cache=not payload.no_cache,
        max_days=max_days,
    )

    # 成功才計次；LLM 失敗時不該扣使用者的額度。
    plan_service.record_qa_usage(db, current_user)

    return {
        "status": "success",
        "result": result,
    }


# ── 個人對話紀錄 ──────────────────────────────────────────────
# 每位使用者只能讀寫自己的對話；別人的對話一律回 404，不透露是否存在。

# 每位使用者保留的未釘選對話上限，超過時刪除最舊的，避免資料表無限成長。
MAX_CONVERSATIONS = 50
# 單一對話的資料上限（約 512 KB），防止異常請求塞爆資料庫。
MAX_CONVERSATION_BYTES = 512 * 1024
CLIENT_ID_PATTERN = r"^[A-Za-z0-9_.-]{1,64}$"


class ConversationPayload(BaseModel):
    title: str = Field(default="", max_length=255)
    keyword: str = Field(default="", max_length=255)
    pinned: bool = False
    manuallyRenamed: bool = False
    dashboardContextId: str = Field(default="", max_length=64)
    createdAt: str | None = None
    updatedAt: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list, max_length=400)


def _find_conversation(db: Session, user_id: int, client_id: str) -> QAConversation | None:
    return (
        db.query(QAConversation)
        .filter(QAConversation.user_id == user_id, QAConversation.client_id == client_id)
        .first()
    )


def _prune_conversations(db: Session, user_id: int) -> None:
    """只保留最近的 MAX_CONVERSATIONS 筆未釘選對話。"""
    stale = (
        db.query(QAConversation)
        .filter(QAConversation.user_id == user_id, QAConversation.pinned == 0)
        .order_by(QAConversation.updated_at.desc(), QAConversation.id.desc())
        .offset(MAX_CONVERSATIONS)
        .all()
    )
    for conversation in stale:
        db.delete(conversation)


@router.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """取得目前使用者自己的對話（釘選優先，其餘依更新時間由新到舊）。"""
    rows = (
        db.query(QAConversation)
        .filter(QAConversation.user_id == current_user.id)
        .order_by(QAConversation.pinned.desc(), QAConversation.updated_at.desc(), QAConversation.id.desc())
        .all()
    )

    return {
        "status": "success",
        "data": {"conversations": [{**row.data, "id": row.client_id} for row in rows]},
    }


@router.put("/conversations/{client_id}")
def save_conversation(
    payload: ConversationPayload,
    client_id: str = Path(..., pattern=CLIENT_ID_PATTERN),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """建立或更新目前使用者的一段對話。"""
    data = {**payload.model_dump(), "id": client_id}

    if len(json.dumps(data, ensure_ascii=False).encode("utf-8")) > MAX_CONVERSATION_BYTES:
        raise HTTPException(status_code=413, detail="對話內容過長，請開啟新對話。")

    now = taiwan_now()
    conversation = _find_conversation(db, current_user.id, client_id)

    if conversation is None:
        conversation = QAConversation(user_id=current_user.id, client_id=client_id, created_at=now)
        db.add(conversation)

    conversation.title = payload.title or "新的對話"
    conversation.pinned = int(payload.pinned)
    conversation.data = data
    conversation.updated_at = now
    db.flush()

    _prune_conversations(db, current_user.id)
    db.commit()

    return {"status": "success"}


@router.delete("/conversations/{client_id}")
def delete_conversation(
    client_id: str = Path(..., pattern=CLIENT_ID_PATTERN),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """刪除目前使用者自己的一段對話。"""
    conversation = _find_conversation(db, current_user.id, client_id)

    if conversation is None:
        raise HTTPException(status_code=404, detail="找不到這段對話。")

    db.delete(conversation)
    db.commit()

    return {"status": "success"}

