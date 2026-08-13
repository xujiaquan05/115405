# backend/app/routers/qa.py

from fastapi import APIRouter, Depends
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import RateLimiter
from app.services.rag_service import answer_question


router = APIRouter(
    prefix="/api/qa",
    tags=["AI Q&A"],
)

# 說明：
# 每個問題會消耗 1-2 次 Gemini 呼叫（花費 API key 額度），
# 因此限制每個 IP 每分鐘 10 個問題，
# 避免 public URL 被灌爆。
qa_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


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
):
    history = [item.model_dump() for item in payload.history] if payload.history else None

    result = answer_question(
        db=db,
        question=payload.question.strip(),
        dashboard_context=payload.dashboard_context,
        history=history,
        use_cache=not payload.no_cache,
    )

    return {
        "status": "success",
        "result": result,
    }
