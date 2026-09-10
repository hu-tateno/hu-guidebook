"""`python -m app.scripts.reembed` — generate Cohere embeddings for chunks missing one.

Pass --all to regenerate every chunk's embedding (e.g. after switching the embed model).
Run locally against the Supabase DATABASE_URL; batches calls to stay well under Cohere's
free-trial rate limits.
"""

from __future__ import annotations

import argparse
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.db.session import SessionLocal
from app.services.cohere_client import embed_texts

_BATCH_SIZE = 90  # keep comfortably under Cohere's per-call text limit


def reembed(db: Session, only_missing: bool = True) -> int:
    stmt = select(Chunk)
    if only_missing:
        stmt = stmt.where(Chunk.embedding.is_(None))
    chunks = db.execute(stmt).scalars().all()

    total = 0
    for i in range(0, len(chunks), _BATCH_SIZE):
        batch = chunks[i : i + _BATCH_SIZE]
        vectors = embed_texts([c.text for c in batch], input_type="search_document")
        for chunk, vector in zip(batch, vectors, strict=True):
            chunk.embedding = vector
        db.commit()
        total += len(batch)
        print(f"embedded {total}/{len(chunks)} chunks")
        if i + _BATCH_SIZE < len(chunks):
            time.sleep(1)  # be gentle with the free-trial rate limit
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Re-embed every chunk, not just ones missing an embedding")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        count = reembed(db, only_missing=not args.all)
        print(f"done: {count} chunks embedded")
    finally:
        db.close()


if __name__ == "__main__":
    main()
