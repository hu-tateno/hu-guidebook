from fastapi.testclient import TestClient

from app.db.models import SearchQuery
from app.db.session import get_db
from app.main import app
from tests.conftest import FakeSession


def test_create_evaluation_records_and_returns_no_device_id():
    search_query = SearchQuery(id=1, admission_year=2024, document_id=1, query_text="休学")
    fake_db = FakeSession(objects=[search_query])
    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)
    try:
        response = client.post(
            "/api/evaluations",
            json={
                "search_query_id": 1,
                "suggestion_helpful": True,
                "answer_resolved": False,
                "category": "休学",
                "comment": "分かりにくかった",
                "device_id": "device-xyz",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    assert response.json() == {"status": "ok"}
    assert "device-xyz" not in response.text

    evaluation = fake_db.added[0]
    assert evaluation.admission_year == 2024
    assert evaluation.device_id == "device-xyz"
    assert evaluation.suggestion_helpful is True
    assert evaluation.answer_resolved is False
    assert fake_db.committed is True


def test_create_evaluation_404_for_unknown_search_query():
    fake_db = FakeSession(objects=[])
    app.dependency_overrides[get_db] = lambda: fake_db
    client = TestClient(app)
    try:
        response = client.post("/api/evaluations", json={"search_query_id": 999})
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 404
