"""Teacher-facing dashboard: metrics, low-rated questions, search traces, CSV export.

Every response here may show search-query text and category (explicit admin features per
README) but must never include an anonymous device_id — see AGENTS.md. Admin endpoints are
disabled entirely (404) unless both ADMIN_PASSWORD and ADMIN_SESSION_SECRET are set.
"""

from __future__ import annotations

import csv
import hmac
import io
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Evaluation, SearchQuery, StageResult
from app.db.session import get_db
from app.scripts.ingest import ingest_all
from app.scripts.reembed import reembed as reembed_chunks
from app.services.admin_auth import COOKIE_NAME, create_session_cookie_value, verify_session_cookie
from app.services.admin_metrics import compute_evaluation_stats

# One-time seed data for the /seed endpoint below — see its docstring.
_SEED_HANDBOOK_DIR = Path(__file__).resolve().parent.parent.parent / "handbook_seed"

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin_enabled() -> None:
    if not get_settings().admin_enabled:
        raise HTTPException(status_code=404, detail="admin API disabled")


def require_admin(admin_session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> None:
    _require_admin_enabled()
    if not verify_session_cookie(admin_session):
        raise HTTPException(status_code=401, detail="admin authentication required")


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(payload: LoginRequest, response: Response) -> dict[str, str]:
    _require_admin_enabled()
    settings = get_settings()
    if not hmac.compare_digest(payload.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="invalid password")
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_cookie_value(),
        httponly=True,
        # web and api are separate Vercel projects on different domains — this is a genuine
        # cross-site request, so SameSite=Lax (which withholds the cookie on fetch/XHR)
        # would silently break admin login. None+Secure is required for that, and requires
        # HTTPS: fine on Vercel, but plain http://localhost dev won't receive this cookie.
        samesite="none",
        secure=True,
        max_age=settings.admin_session_hours * 3600,
    )
    return {"status": "ok"}


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(COOKIE_NAME, samesite="none", secure=True)
    return {"status": "ok"}


@router.get("/metrics")
def metrics(
    admission_year: int | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> dict:
    search_stmt = select(SearchQuery.id)
    if admission_year is not None:
        search_stmt = search_stmt.where(SearchQuery.admission_year == admission_year)
    total_searches = len(db.execute(search_stmt).all())

    eval_stmt = select(Evaluation.suggestion_helpful, Evaluation.answer_resolved)
    if admission_year is not None:
        eval_stmt = eval_stmt.where(Evaluation.admission_year == admission_year)
    if category is not None:
        eval_stmt = eval_stmt.where(Evaluation.category == category)
    rows = db.execute(eval_stmt).all()

    helpful_flags = [r[0] for r in rows if r[0] is not None]
    resolved_flags = [r[1] for r in rows if r[1] is not None]
    return asdict(compute_evaluation_stats(total_searches, helpful_flags, resolved_flags))


@router.get("/low-rated-questions")
def low_rated_questions(
    admission_year: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> list[dict]:
    stmt = (
        select(
            Evaluation.id,
            Evaluation.admission_year,
            Evaluation.category,
            Evaluation.suggestion_helpful,
            Evaluation.answer_resolved,
            Evaluation.comment,
            Evaluation.created_at,
            SearchQuery.query_text,
        )
        .join(SearchQuery, SearchQuery.id == Evaluation.search_query_id)
        .where((Evaluation.suggestion_helpful.is_(False)) | (Evaluation.answer_resolved.is_(False)))
    )
    if admission_year is not None:
        stmt = stmt.where(Evaluation.admission_year == admission_year)
    stmt = stmt.order_by(Evaluation.created_at.desc()).limit(limit)

    rows = db.execute(stmt).all()
    return [
        {
            "evaluation_id": r.id,
            "admission_year": r.admission_year,
            "category": r.category,
            "suggestion_helpful": r.suggestion_helpful,
            "answer_resolved": r.answer_resolved,
            "comment": r.comment,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "query_text": r.query_text,
        }
        for r in rows
    ]


@router.get("/search-traces/{search_query_id}")
def search_trace(
    search_query_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> dict:
    search_query = db.get(SearchQuery, search_query_id)
    if search_query is None:
        raise HTTPException(status_code=404, detail="search query not found")
    stages = (
        db.query(StageResult)
        .filter(StageResult.search_query_id == search_query_id)
        .order_by(StageResult.stage)
        .all()
    )
    return {
        "search_query_id": search_query.id,
        "admission_year": search_query.admission_year,
        "query_text": search_query.query_text,
        "created_at": search_query.created_at.isoformat() if search_query.created_at else None,
        "stages": [{"stage": s.stage, "label": s.label, "payload": s.payload} for s in stages],
    }


@router.get("/export.csv")
def export_csv(
    admission_year: int | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> StreamingResponse:
    stmt = select(
        Evaluation.id,
        Evaluation.admission_year,
        Evaluation.category,
        Evaluation.suggestion_helpful,
        Evaluation.answer_resolved,
        Evaluation.comment,
        Evaluation.created_at,
        SearchQuery.query_text,
    ).join(SearchQuery, SearchQuery.id == Evaluation.search_query_id)
    if admission_year is not None:
        stmt = stmt.where(Evaluation.admission_year == admission_year)
    rows = db.execute(stmt).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["evaluation_id", "admission_year", "category", "suggestion_helpful", "answer_resolved", "comment", "created_at", "query_text"]
    )
    for r in rows:
        writer.writerow(
            [r.id, r.admission_year, r.category, r.suggestion_helpful, r.answer_resolved, r.comment,
             r.created_at.isoformat() if r.created_at else "", r.query_text]
        )
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=evaluations.csv"}
    )


@router.get("/seed")
def seed(
    token: str,
    embed_all: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    """One-time bootstrap: ingest handbook_seed/*.pdf (bundled into this Vercel function
    specifically so this endpoint can reach them — see api/AGENTS.md) and embed any chunk
    missing a vector. Safe to call more than once: ingestion upserts by admission_year via
    content hash, and embedding only fills gaps (embed_all=true forces re-embedding
    everything, e.g. after switching Cohere's embed model). If a call times out partway
    through, just call it again — both steps pick up where they left off.

    GET with a `token` query param (checked against ADMIN_SESSION_SECRET) rather than the
    normal cookie-based admin session, so this can be triggered with a single URL fetch —
    there's no way to drive a POST + cookie login from outside this deployment's own request
    tooling. Remove this endpoint once the target DB has been seeded (see api/AGENTS.md); a
    secret in a URL query string is an acceptable one-time bootstrap tradeoff, not a pattern
    to keep around.
    """
    settings = get_settings()
    if not settings.admin_enabled or not hmac.compare_digest(token, settings.admin_session_secret):
        raise HTTPException(status_code=401, detail="invalid token")
    documents_ingested = ingest_all(db, _SEED_HANDBOOK_DIR)
    chunks_embedded = reembed_chunks(db, only_missing=not embed_all)
    return {"documents_ingested": documents_ingested, "chunks_embedded": chunks_embedded}
