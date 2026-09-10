from pathlib import Path

from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.models import Document
from app.db.session import get_db
from app.main import app
from tests.conftest import FakeSession


def test_list_documents_returns_expected_fields():
    documents = [
        Document(
            id=1, admission_year=2024, title="2024年度 履修の手引き",
            source_filename="management_guidance2024.pdf", content_hash="x" * 64, page_count=55,
        ),
        Document(
            id=2, admission_year=2025, title="2025年度 履修の手引き",
            source_filename="management_guidance2025.pdf", content_hash="y" * 64, page_count=60,
        ),
    ]
    fake_db = FakeSession(objects=documents)
    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)
    try:
        response = client.get("/api/documents")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "id": 1, "admission_year": 2024, "title": "2024年度 履修の手引き", "page_count": 55,
            "source_filename": "management_guidance2024.pdf",
        },
        {
            "id": 2, "admission_year": 2025, "title": "2025年度 履修の手引き", "page_count": 60,
            "source_filename": "management_guidance2025.pdf",
        },
    ]


def test_get_document_file_streams_pdf(tmp_path: Path, monkeypatch):
    pdf_path = tmp_path / "management_guidance2024.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake pdf bytes")
    monkeypatch.setattr(get_settings(), "handbook_dir", str(tmp_path))

    document = Document(
        id=1, admission_year=2024, title="2024年度 履修の手引き",
        source_filename="management_guidance2024.pdf", content_hash="x" * 64, page_count=55,
    )
    fake_db = FakeSession(objects=[document])
    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)
    try:
        response = client.get("/api/documents/1/file")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4 fake pdf bytes"


def test_get_document_file_404_for_unknown_document():
    fake_db = FakeSession(objects=[])
    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)
    try:
        response = client.get("/api/documents/999/file")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 404


def test_get_document_file_404_when_pdf_missing_on_disk(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(get_settings(), "handbook_dir", str(tmp_path))
    document = Document(
        id=1, admission_year=2024, title="2024年度 履修の手引き",
        source_filename="missing.pdf", content_hash="x" * 64, page_count=55,
    )
    fake_db = FakeSession(objects=[document])
    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)
    try:
        response = client.get("/api/documents/1/file")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 404
