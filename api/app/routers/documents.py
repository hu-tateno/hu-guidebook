from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Document
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["documents"])


class DocumentOut(BaseModel):
    id: int
    admission_year: int
    title: str
    page_count: int
    source_filename: str


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentOut]:
    docs = db.query(Document).order_by(Document.admission_year.desc()).all()
    return [
        DocumentOut(
            id=d.id,
            admission_year=d.admission_year,
            title=d.title,
            page_count=d.page_count,
            source_filename=d.source_filename,
        )
        for d in docs
    ]


@router.get("/documents/{document_id}/file")
def get_document_file(document_id: int, db: Session = Depends(get_db)) -> FileResponse:
    """Serve the source PDF from disk. On the Vercel deployment profile the frontend instead
    fetches these PDFs directly from web/public/handbook/ (a Vercel Python function only
    bundles files under its own project root, so this endpoint can't see that directory
    there) — this stays as a fallback for deployment profiles where the whole repo checkout
    is on disk next to the API process (local dev, Render).
    """
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    path = Path(get_settings().handbook_dir) / document.source_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="source PDF not found on disk")
    return FileResponse(path, media_type="application/pdf", filename=document.source_filename)
