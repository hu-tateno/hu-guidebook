from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import Evaluation, SearchQuery
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["evaluation"])


class EvaluationRequest(BaseModel):
    search_query_id: int
    suggestion_helpful: bool | None = None
    answer_resolved: bool | None = None
    category: str | None = Field(default=None, max_length=100)
    comment: str | None = Field(default=None, max_length=2000)
    device_id: str | None = Field(default=None, max_length=64)


@router.post("/evaluations", status_code=201)
def create_evaluation(payload: EvaluationRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    search_query = db.get(SearchQuery, payload.search_query_id)
    if search_query is None:
        raise HTTPException(status_code=404, detail="search query not found")
    db.add(
        Evaluation(
            search_query_id=search_query.id,
            admission_year=search_query.admission_year,
            category=payload.category,
            suggestion_helpful=payload.suggestion_helpful,
            answer_resolved=payload.answer_resolved,
            comment=payload.comment,
            device_id=payload.device_id,
        )
    )
    db.commit()
    return {"status": "ok"}
