"""Stateless, signed-cookie admin sessions (no admin_sessions DB table needed).

8-hour expiry per README ("管理者セッションは8時間で失効"), enforced by itsdangerous'
TimestampSigner max_age check. The cookie payload carries no information beyond "this is a
valid admin session" — there's nothing else to check once the signature verifies.
"""

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from app.config import get_settings

COOKIE_NAME = "admin_session"
_SESSION_VALUE = "admin"


def _signer() -> TimestampSigner:
    return TimestampSigner(get_settings().admin_session_secret)


def create_session_cookie_value() -> str:
    return _signer().sign(_SESSION_VALUE).decode("utf-8")


def verify_session_cookie(value: str | None) -> bool:
    if not value:
        return False
    try:
        _signer().unsign(value, max_age=get_settings().admin_session_hours * 3600)
        return True
    except (BadSignature, SignatureExpired):
        return False
