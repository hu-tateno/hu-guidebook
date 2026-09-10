from pathlib import Path

import pymupdf
import pytest

from app.services.ingest import (
    admission_year_from_filename,
    build_document_draft,
    extract_chunks,
    split_long_text,
)


def test_admission_year_from_filename():
    assert admission_year_from_filename("management_guidance2024.pdf") == 2024
    assert admission_year_from_filename("2026-handbook.pdf") == 2026


def test_admission_year_from_filename_raises_without_year():
    with pytest.raises(ValueError):
        admission_year_from_filename("handbook.pdf")


def test_split_long_text_keeps_short_text_whole():
    assert split_long_text("short text", max_chars=100) == ["short text"]


def test_split_long_text_wraps_long_paragraph():
    text = "a" * 2500
    parts = split_long_text(text, max_chars=1000)
    assert len(parts) == 3
    assert all(len(p) <= 1000 for p in parts)
    assert "".join(parts) == text


def test_split_long_text_splits_on_paragraph_breaks():
    text = "para one\npara two"
    assert split_long_text(text, max_chars=100) == ["para one\npara two"]  # fits whole
    assert split_long_text("x" * 5 + "\n" + "y" * 5, max_chars=5) == ["xxxxx", "yyyyy"]


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Leave of Absence")
    page.insert_text((72, 100), "To request a leave of absence, submit the form to the office.")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Graduation Requirements need at least 124 credits total.")
    pdf_path = tmp_path / "management_guidance2024.pdf"
    doc.save(pdf_path)
    doc.close()
    return pdf_path


def test_extract_chunks_merges_nearby_blocks_on_a_page(sample_pdf: Path):
    page_count, chunks = extract_chunks(sample_pdf)
    assert page_count == 2
    # the two short blocks on page 1 are merged into one chunk; page 2 stays its own chunk
    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert "Leave of Absence" in chunks[0].text
    assert "submit the form" in chunks[0].text
    assert len(chunks[0].bbox) == 4
    assert chunks[-1].page_number == 2
    assert "124 credits" in chunks[-1].text


def test_extract_chunks_starts_new_chunk_past_target_size(tmp_path: Path):
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for i in range(10):
        page.insert_text((72, y), "x" * 80)
        y += 20
    pdf_path = tmp_path / "management_guidance2023.pdf"
    doc.save(pdf_path)
    doc.close()

    _, chunks = extract_chunks(pdf_path)
    # 10 blocks * 80 chars = 800 chars > _TARGET_CHUNK_CHARS(500), so it must split into 2+
    assert len(chunks) >= 2
    assert all(len(c.text) <= 1200 for c in chunks)


def test_build_document_draft(sample_pdf: Path):
    draft = build_document_draft(sample_pdf)
    assert draft.admission_year == 2024
    assert draft.source_filename == "management_guidance2024.pdf"
    assert draft.page_count == 2
    assert len(draft.chunks) == 2
    assert len(draft.content_hash) == 64  # sha256 hex digest
