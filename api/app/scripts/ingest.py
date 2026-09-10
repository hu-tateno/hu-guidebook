"""`python -m app.scripts.ingest` — (re)ingest every PDF in HANDBOOK_DIR into the DB.

Run locally against the Supabase DATABASE_URL (see README "クラウドへのデプロイ"); the
deployed Render API does not run this at request time. Embeddings are generated separately
by app.scripts.reembed so this step never depends on the Cohere API.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from app.services.ingest import build_document_draft


def ingest_all(db: Session, handbook_dir: Path) -> int:
    pdf_paths = sorted(handbook_dir.glob("*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found in {handbook_dir}", file=sys.stderr)
        return 0

    ingested = 0
    for pdf_path in pdf_paths:
        draft = build_document_draft(pdf_path)
        existing = db.query(Document).filter(Document.admission_year == draft.admission_year).one_or_none()
        if existing and existing.content_hash == draft.content_hash:
            print(f"{pdf_path.name}: unchanged, skipping")
            continue
        if existing:
            db.delete(existing)
            db.flush()

        document = Document(
            admission_year=draft.admission_year,
            title=draft.title,
            source_filename=draft.source_filename,
            content_hash=draft.content_hash,
            page_count=draft.page_count,
        )
        db.add(document)
        db.flush()

        for chunk_draft in draft.chunks:
            db.add(
                Chunk(
                    document_id=document.id,
                    admission_year=document.admission_year,
                    page_number=chunk_draft.page_number,
                    text=chunk_draft.text,
                    char_count=len(chunk_draft.text),
                    bbox=chunk_draft.bbox,
                )
            )
        db.commit()
        ingested += 1
        print(f"{pdf_path.name}: ingested {len(draft.chunks)} chunks (admission_year={draft.admission_year})")

    return ingested


def main() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        ingest_all(db, Path(settings.handbook_dir))
    finally:
        db.close()


if __name__ == "__main__":
    main()
