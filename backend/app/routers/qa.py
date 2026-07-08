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

# Note:
# Mỗi câu hỏi tốn 1-2 call Gemini (tốn quota API key),
# nên giới hạn mỗi IP 10 câu hỏi / phút để tránh bị spam
# trên URL public.
qa_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)
    dashboard_context: dict[str, Any] | None = None


@router.post("/ask", dependencies=[Depends(qa_rate_limiter)])
def ask_question(
    payload: QuestionRequest,
    db: Session = Depends(get_db),
):
    result = answer_question(
        db=db,
        question=payload.question.strip(),
        dashboard_context=payload.dashboard_context,
    )

    return {
        "status": "success",
        "result": result,
    }
