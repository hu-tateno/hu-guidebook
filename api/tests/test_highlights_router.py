from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db.models import Chunk
from app.db.session import get_db
from app.main import app
from app.routers.highlights import PopularHighlightOut, shape_popular_highlights
from tests.conftest import FakeSession


def _chunk(id_=1, page=3, text="休学を希望する場合は休学願を提出してください。", document_id=1, admission_year=2024):
    return Chunk(
        id=id_, document_id=document_id, admission_year=admission_year, page_number=page,
        heading_path=None, text=text, char_count=len(text), bbox=[1.0, 2.0, 3.0, 4.0],
    )


def test_shape_popular_highlights_sorts_by_count_desc_and_respects_limit():
    chunks_by_id = {1: _chunk(1), 2: _chunk(2, page=5, text="卒業要件は124単位です。")}
    counts = [(1, 3), (2, 7)]
    result = shape_popular_highlights(counts, chunks_by_id, limit=10)
    assert [r.chunk_id for r in result] == [2, 1]
    assert result[0].count == 7
    assert result[0].page_number == 5


def test_shape_popular_highlights_respects_limit():
    chunks_by_id = {i: _chunk(i) for i in range(5)}
    counts = [(i, i) for i in range(5)]
    result = shape_popular_highlights(counts, chunks_by_id, limit=2)
    assert len(result) == 2
    assert result[0].count == 4  # highest count first


def test_shape_popular_highlights_skips_missing_chunks():
    counts = [(1, 5), (99, 9)]  # chunk 99 not in chunks_by_id (e.g. deleted)
    result = shape_popular_highlights(counts, {1: _chunk(1)}, limit=10)
    assert [r.chunk_id for r in result] == [1]


def test_popular_highlight_schema_never_carries_device_id_or_question_or_answer():
    fields = set(PopularHighlightOut.model_fields.keys())
    assert fields == {"chunk_id", "page_number", "text", "count"}
    assert "device_id" not in fields
    assert "query" not in fields
    assert "answer" not in fields


def test_create_highlight_records_and_returns_no_device_id():
    chunk = _chunk()
    fake_db = FakeSession(objects=[chunk])
    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)
    try:
        response = client.post("/api/highlights", json={"chunk_id": 1, "device_id": "device-xyz"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    assert response.json() == {"status": "ok"}
    assert "device-xyz" not in response.text
    highlight = fake_db.added[0]
    assert highlight.device_id == "device-xyz"
    assert highlight.admission_year == 2024
    assert highlight.document_id == 1
    assert fake_db.committed is True


def test_create_highlight_404_for_unknown_chunk():
    fake_db = FakeSession(objects=[])
    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)
    try:
        response = client.post("/api/highlights", json={"chunk_id": 42, "device_id": "device-xyz"})
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 404


def test_popular_highlights_endpoint_never_leaks_device_id():
    chunk = _chunk()
    fake_db = MagicMock()
    count_result = MagicMock()
    count_result.all.return_value = [(1, 4)]
    chunk_result = MagicMock()
    chunk_result.scalars.return_value.all.return_value = [chunk]
    fake_db.execute.side_effect = [count_result, chunk_result]

    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)
    try:
        response = client.get("/api/highlights/popular", params={"admission_year": 2024})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body == [{"chunk_id": 1, "page_number": 3, "text": chunk.text, "count": 4}]
    assert "device_id" not in response.text
    assert "device-xyz" not in response.text
