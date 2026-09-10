"""Vercel Python Serverless Functions entrypoint.

Vercel's zero-config Python runtime looks for .py files under <root>/api/ and wraps an
exported ASGI `app` automatically. Our actual FastAPI app lives in app/main.py — this file
just re-exports it so Vercel can find it at the conventional path.
"""

from app.main import app  # noqa: F401
