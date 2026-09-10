"""PDF -> chunk-draft extraction (Stage 0, upstream of the search pipeline).

Pure parsing/chunking logic lives here, independent of the database, so it can be unit
tested directly. app/scripts/ingest.py wraps this with the DB writes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

_YEAR_RE = re.compile(r"(20\d{2})")
_TARGET_CHUNK_CHARS = 500  # merge consecutive text blocks up to about this size
_MAX_CHUNK_CHARS = 1200  # hard cap; oversized single blocks are hard-split
_MIN_CHUNK_CHARS = 10


@dataclass(frozen=True)
class ChunkDraft:
    page_number: int
    text: str
    bbox: list[float]  # [x0, y0, x1, y1] in PDF points, top-left origin


@dataclass(frozen=True)
class DocumentDraft:
    admission_year: int
    title: str
    source_filename: str
    content_hash: str
    page_count: int
    chunks: list[ChunkDraft]


def admission_year_from_filename(filename: str) -> int:
    match = _YEAR_RE.search(filename)
    if not match:
        raise ValueError(f"could not determine admission year from filename: {filename}")
    return int(match.group(1))


def split_long_text(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """Split on paragraph breaks first, then hard-wrap anything still too long."""
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        while len(paragraph) > max_chars:
            parts.append(paragraph[:max_chars])
            paragraph = paragraph[max_chars:]
        if paragraph:
            parts.append(paragraph)
    return parts or [text[:max_chars]]


def _union_bbox(a: list[float], b: list[float]) -> list[float]:
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def extract_chunks(pdf_path: Path) -> tuple[int, list[ChunkDraft]]:
    """Merge consecutive text blocks on a page into ~paragraph-sized chunks (bbox = the
    union of the merged blocks' boxes), so chunks carry enough context for embedding/rerank
    instead of one chunk per raw PDF text fragment. A single block larger than
    _MAX_CHUNK_CHARS (e.g. a dense table cell) is flushed and hard-split on its own."""
    doc = pymupdf.open(pdf_path)
    try:
        chunks: list[ChunkDraft] = []
        for page_index in range(doc.page_count):
            page = doc[page_index]
            buffer_texts: list[str] = []
            buffer_bbox: list[float] | None = None

            def flush() -> None:
                if not buffer_texts:
                    return
                text = "\n".join(buffer_texts).strip()
                if len(text) >= _MIN_CHUNK_CHARS:
                    chunks.append(ChunkDraft(page_number=page_index + 1, text=text, bbox=list(buffer_bbox)))

            for block in page.get_text("blocks"):
                x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
                text = text.strip()
                if not text:
                    continue
                bbox = [x0, y0, x1, y1]

                if len(text) > _MAX_CHUNK_CHARS:
                    flush()
                    buffer_texts, buffer_bbox = [], None
                    for piece in split_long_text(text):
                        piece = piece.strip()
                        if len(piece) >= _MIN_CHUNK_CHARS:
                            chunks.append(ChunkDraft(page_number=page_index + 1, text=piece, bbox=bbox))
                    continue

                current_len = sum(len(t) for t in buffer_texts)
                if buffer_texts and current_len + len(text) > _TARGET_CHUNK_CHARS:
                    flush()
                    buffer_texts, buffer_bbox = [], None

                buffer_texts.append(text)
                buffer_bbox = bbox if buffer_bbox is None else _union_bbox(buffer_bbox, bbox)

            flush()
        return doc.page_count, chunks
    finally:
        doc.close()


def build_document_draft(pdf_path: Path) -> DocumentDraft:
    admission_year = admission_year_from_filename(pdf_path.name)
    content_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    page_count, chunks = extract_chunks(pdf_path)
    return DocumentDraft(
        admission_year=admission_year,
        title=f"{admission_year}年度 履修の手引き",
        source_filename=pdf_path.name,
        content_hash=content_hash,
        page_count=page_count,
        chunks=chunks,
    )
