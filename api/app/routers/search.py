from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import Document, SearchQuery, StageResult
from app.db.session import get_db
from app.services.search.pipeline import run_search

router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    admission_year: int
    document_id: int | None = None
    query: str = Field(min_length=1, max_length=500)
    device_id: str | None = Field(default=None, max_length=64)
    want_answer: bool = True


class ChunkOut(BaseModel):
    chunk_id: int
    document_id: int
    page_number: int
    text: str
    bbox: list[float]
    score: float
    matched_terms: list[str]


class StageTraceOut(BaseModel):
    stage: int
    label: str
    query_terms: list[str]
    result_count: int


class SearchResponse(BaseModel):
    search_query_id: int
    admission_year: int
    document_id: int
    query: str
    stages: list[StageTraceOut]
    results: list[ChunkOut]
    answer: str | None


def _resolve_document(db: Session, admission_year: int, document_id: int | None) -> Document:
    if document_id is not None:
        document = db.get(Document, document_id)
        if document is None or document.admission_year != admission_year:
            raise HTTPException(status_code=404, detail="document not found for this admission_year")
        return document
    document = db.query(Document).filter(Document.admission_year == admission_year).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="no document ingested for this admission_year")
    return document


@router.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must not be blank")

    document = _resolve_document(db, payload.admission_year, payload.document_id)

    result = run_search(
        db, payload.admission_year, document.id, query, want_answer=payload.want_answer
    )

    search_query = SearchQuery(
        admission_year=payload.admission_year,
        document_id=document.id,
        query_text=query,
        device_id=payload.device_id,
    )
    db.add(search_query)
    db.flush()
    for stage in result.stages:
        db.add(
            StageResult(
                search_query_id=search_query.id,
                stage=stage.stage,
                label=stage.label,
                payload={
                    "query_terms": stage.query_terms,
                    "result_count": stage.result_count,
                    "top_chunk_ids": stage.top_chunk_ids,
                },
            )
        )
    db.commit()

    return SearchResponse(
        search_query_id=search_query.id,
        admission_year=payload.admission_year,
        document_id=document.id,
        query=query,
        stages=[
            StageTraceOut(stage=s.stage, label=s.label, query_terms=s.query_terms, result_count=s.result_count)
            for s in result.stages
        ],
        results=[
            ChunkOut(
                chunk_id=sc.chunk.id,
                document_id=sc.chunk.document_id,
                page_number=sc.chunk.page_number,
                text=sc.chunk.text,
                bbox=sc.chunk.bbox,
                score=sc.score,
                matched_terms=sc.matched_terms,
            )
            for sc in result.final_results
        ],
        answer=result.answer,
    )
