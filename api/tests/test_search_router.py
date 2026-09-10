from fastapi.testclient import TestClient

from app.db.models import Document
from app.db.session import get_db
from app.main import app
from app.routers import search as search_router
from app.services.search.pipeline import ChunkRecord, ScoredChunk, SearchRunResult, StageTrace
from tests.conftest import FakeSession


def _make_document(id_=1, admission_year=2024):
    return Document(
        id=id_,
        admission_year=admission_year,
        title=f"{admission_year}年度 履修の手引き",
        source_filename=f"management_guidance{admission_year}.pdf",
        content_hash="x" * 64,
        page_count=10,
    )


def _canned_result(admission_year=2024, document_id=1):
    chunk = ChunkRecord(
        id=1, document_id=document_id, admission_year=admission_year, page_number=3,
        heading_path=None, text="休学を希望する場合は休学願を提出してください。", bbox=[1.0, 2.0, 3.0, 4.0],
    )
    return SearchRunResult(
        query="休学",
        admission_year=admission_year,
        document_id=document_id,
        stages=[StageTrace(stage=1, label="literal", query_terms=["休学"], result_count=1, top_chunk_ids=[1])],
        final_results=[ScoredChunk(chunk=chunk, score=0.9, matched_terms=["休学"])],
        answer="休学願を学務課に提出してください。[1]",
    )


def test_search_endpoint_returns_results_and_persists_query(monkeypatch):
    document = _make_document()
    fake_db = FakeSession(objects=[document])
    app.dependency_overrides[get_db] = lambda: fake_db
    monkeypatch.setattr(search_router, "run_search", lambda *a, **k: _canned_result())

    client = TestClient(app)
    try:
        response = client.post(
            "/api/search",
            json={"admission_year": 2024, "query": "休学", "device_id": "device-abc"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["admission_year"] == 2024
    assert body["document_id"] == 1
    assert body["answer"].startswith("休学願")
    assert len(body["results"]) == 1
    assert body["results"][0]["chunk_id"] == 1
    assert "device_id" not in body  # never echo the anonymous device id back

    # a SearchQuery and its StageResult rows were persisted (added to the session)
    added_types = {type(obj).__name__ for obj in fake_db.added}
    assert "SearchQuery" in added_types
    assert "StageResult" in added_types
    assert fake_db.committed is True


def test_search_endpoint_404_for_unknown_admission_year():
    fake_db = FakeSession(objects=[])
    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)
    try:
        response = client.post("/api/search", json={"admission_year": 1999, "query": "休学"})
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 404


def test_search_endpoint_422_for_blank_query():
    fake_db = FakeSession(objects=[_make_document()])
    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)
    try:
        response = client.post("/api/search", json={"admission_year": 2024, "query": "   "})
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 422
