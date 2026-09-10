from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


def _client_with_db(fake_db):
    app.dependency_overrides[get_db] = lambda: fake_db
    return TestClient(app)


def test_admin_disabled_returns_404_for_login(admin_disabled):
    client = _client_with_db(MagicMock())
    try:
        response = client.post("/api/admin/login", json={"password": "whatever"})
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 404


def test_login_wrong_password_401(admin_settings):
    client = _client_with_db(MagicMock())
    try:
        response = client.post("/api/admin/login", json={"password": "not-the-password"})
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 401


def test_login_correct_password_sets_cookie(admin_settings):
    client = _client_with_db(MagicMock())
    try:
        response = client.post("/api/admin/login", json={"password": "test-admin-pw"})
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    assert "admin_session" in response.cookies


def test_metrics_requires_admin_session(admin_settings):
    client = _client_with_db(MagicMock())
    try:
        response = client.get("/api/admin/metrics")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 401


def test_metrics_with_valid_session_returns_stats(admin_settings):
    fake_db = MagicMock()
    searches_result = MagicMock()
    searches_result.all.return_value = [(1,), (2,), (3,)]
    evals_result = MagicMock()
    evals_result.all.return_value = [(True, False), (True, True)]
    fake_db.execute.side_effect = [searches_result, evals_result]

    client = _client_with_db(fake_db)
    try:
        login = client.post("/api/admin/login", json={"password": "test-admin-pw"})
        response = client.get("/api/admin/metrics")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert login.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body["total_searches"] == 3
    assert body["total_evaluations"] == 2
    assert body["helpful_rate"] == 1.0
    assert body["resolved_rate"] == 0.5


def test_low_rated_questions_never_leaks_device_id(admin_settings):
    fake_db = MagicMock()
    row = MagicMock()
    row.id = 1
    row.admission_year = 2024
    row.category = "休学"
    row.suggestion_helpful = False
    row.answer_resolved = None
    row.comment = "わかりにくい"
    row.created_at = None
    row.query_text = "休学したい"
    fake_db.execute.return_value.all.return_value = [row]

    client = _client_with_db(fake_db)
    try:
        client.post("/api/admin/login", json={"password": "test-admin-pw"})
        response = client.get("/api/admin/low-rated-questions")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert "device_id" not in response.text
    body = response.json()
    assert body[0]["query_text"] == "休学したい"
    assert "device_id" not in body[0]


def test_export_csv_never_includes_device_id(admin_settings):
    fake_db = MagicMock()
    row = MagicMock()
    row.id = 1
    row.admission_year = 2024
    row.category = "休学"
    row.suggestion_helpful = True
    row.answer_resolved = True
    row.comment = None
    row.created_at = None
    row.query_text = "休学したい"
    fake_db.execute.return_value.all.return_value = [row]

    client = _client_with_db(fake_db)
    try:
        client.post("/api/admin/login", json={"password": "test-admin-pw"})
        response = client.get("/api/admin/export.csv")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert "device_id" not in response.text
    assert "device-" not in response.text
    assert "query_text" in response.text
