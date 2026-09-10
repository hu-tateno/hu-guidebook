import time

from app.services.admin_auth import create_session_cookie_value, verify_session_cookie


def test_valid_cookie_round_trips(admin_settings):
    cookie = create_session_cookie_value()
    assert verify_session_cookie(cookie) is True


def test_missing_cookie_is_invalid(admin_settings):
    assert verify_session_cookie(None) is False
    assert verify_session_cookie("") is False


def test_tampered_cookie_is_invalid(admin_settings):
    cookie = create_session_cookie_value()
    assert verify_session_cookie(cookie + "x") is False


def test_expired_cookie_is_invalid(admin_settings, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ADMIN_SESSION_HOURS", "0")
    get_settings.cache_clear()
    cookie = create_session_cookie_value()
    time.sleep(1.1)
    assert verify_session_cookie(cookie) is False
    get_settings.cache_clear()
