# backend/app/routers/qa.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.rag_service import answer_question


router = APIRouter(
    prefix="/api/qa",
    tags=["AI Q&A"],
)


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)


@router.post("/ask")
def ask_question(
    payload: QuestionRequest,
    db: Session = Depends(get_db),
):
    result = answer_question(db=db, question=payload.question.strip())

    return {
        "status": "success",
        "result": result,
    }
