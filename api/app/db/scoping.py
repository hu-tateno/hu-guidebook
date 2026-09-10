"""Single sanctioned entry points for reading chunks/highlights.

AGENTS.md requires strict admission-year/document-id separation in every search,
highlight, and aggregate query. Rather than trust every call site to remember the
filter, all reads go through these helpers so the constraint lives in one place
and is covered by tests/test_scoping.py.
"""

from sqlalchemy import Select, select

from app.db.models import Chunk, Highlight


def scoped_chunk_query(admission_year: int, document_id: int | None = None) -> Select:
    if admission_year is None:
        raise ValueError("admission_year is required to query chunks")
    stmt = select(Chunk).where(Chunk.admission_year == admission_year)
    if document_id is not None:
        stmt = stmt.where(Chunk.document_id == document_id)
    return stmt


def scoped_highlight_query(admission_year: int, document_id: int | None = None) -> Select:
    if admission_year is None:
        raise ValueError("admission_year is required to query highlights")
    stmt = select(Highlight).where(Highlight.admission_year == admission_year)
    if document_id is not None:
        stmt = stmt.where(Highlight.document_id == document_id)
    return stmt
