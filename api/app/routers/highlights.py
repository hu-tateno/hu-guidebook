"""Highlight recording + popular-highlight aggregation.

AGENTS.md: "Never expose anonymous device IDs, full questions, or answers through
popular-highlight endpoints." Popular-highlight results below carry only chunk_id/page/text
(the handbook passage itself, which is public course content) and an aggregate count of
distinct devices — never a device_id, and this endpoint never touches SearchQuery/Evaluation
so it structurally cannot leak a question or an AI answer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Highlight
from app.db.scoping import scoped_chunk_query
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["highlights"])


class HighlightRequest(BaseModel):
    chunk_id: int
    device_id: str = Field(min_length=1, max_length=64)


class PopularHighlightOut(BaseModel):
    chunk_id: int
    page_number: int
    text: str
    count: int


def shape_popular_highlights(
    counts: list[tuple[int, int]], chunks_by_id: dict[int, Chunk], limit: int
) -> list[PopularHighlightOut]:
    """Pure: join aggregate counts with chunk rows and cap at `limit`. Split out from the
    endpoint so the shaping/ordering logic is unit-testable without a database."""
    out = []
    for chunk_id, count in counts:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        out.append(PopularHighlightOut(chunk_id=chunk.id, page_number=chunk.page_number, text=chunk.text, count=count))
    out.sort(key=lambda h: h.count, reverse=True)
    return out[:limit]


@router.post("/highlights", status_code=201)
def create_highlight(payload: HighlightRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    chunk = db.get(Chunk, payload.chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="chunk not found")
    db.add(
        Highlight(
            chunk_id=chunk.id,
            admission_year=chunk.admission_year,
            document_id=chunk.document_id,
            device_id=payload.device_id,
        )
    )
    db.commit()
    return {"status": "ok"}


@router.get("/highlights/popular", response_model=list[PopularHighlightOut])
def popular_highlights(
    admission_year: int,
    document_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[PopularHighlightOut]:
    count_stmt = (
        select(Highlight.chunk_id, func.count(func.distinct(Highlight.device_id)))
        .where(Highlight.admission_year == admission_year)
    )
    if document_id is not None:
        count_stmt = count_stmt.where(Highlight.document_id == document_id)
    count_stmt = count_stmt.group_by(Highlight.chunk_id)

    counts = db.execute(count_stmt).all()
    if not counts:
        return []

    chunk_ids = [row[0] for row in counts]
    chunk_rows = db.execute(
        scoped_chunk_query(admission_year, document_id).where(Chunk.id.in_(chunk_ids))
    ).scalars().all()
    chunks_by_id = {c.id: c for c in chunk_rows}

    return shape_popular_highlights([(row[0], row[1]) for row in counts], chunks_by_id, limit)
