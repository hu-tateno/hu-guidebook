import importlib

from app.config import Settings


def test_blank_numeric_env_vars_fall_back_to_defaults(monkeypatch):
    """Vercel's "detected env vars" import UI can create an env var with an empty string
    instead of omitting it (see api/AGENTS.md deploy notes). That must not crash Settings."""
    monkeypatch.setenv("COHERE_TIMEOUT_SECONDS", "")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "")
    monkeypatch.setenv("ADMIN_SESSION_HOURS", "")

    settings = Settings()

    assert settings.cohere_timeout_seconds == 20.0
    assert settings.embedding_dimensions == 1024
    assert settings.admin_session_hours == 8


def test_non_blank_numeric_env_vars_still_apply(monkeypatch):
    monkeypatch.setenv("COHERE_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "256")

    settings = Settings()

    assert settings.cohere_timeout_seconds == 5.0
    assert settings.embedding_dimensions == 256


def test_module_importable_after_reload():
    # smoke test: reload shouldn't error (catches accidental import-time exceptions)
    import app.config

    importlib.reload(app.config)
