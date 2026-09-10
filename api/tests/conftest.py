"""Test doubles shared across router tests.

None of these tests touch a real database: FakeSession implements just enough of the
SQLAlchemy Session interface for the specific queries app/routers/*.py issues, pre-loaded
with the exact rows each test needs. Real DB/pgvector behavior is out of scope for this
sandbox — see AGENTS.md "Verification".
"""

from __future__ import annotations

import pytest

from app.config import get_settings


@pytest.fixture
def admin_settings(monkeypatch):
    """Enable the admin API with known password/secret, restoring prior state afterwards."""
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-pw")
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-admin-secret")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def admin_disabled(monkeypatch):
    """Explicitly clear admin credentials so admin_enabled is False."""
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


class _FakeQuery:
    def __init__(self, items: list):
        self._items = items

    def filter(self, *args, **kwargs) -> "_FakeQuery":
        return self

    def order_by(self, *args, **kwargs) -> "_FakeQuery":
        return self

    def one_or_none(self):
        return self._items[0] if self._items else None

    def all(self) -> list:
        return list(self._items)


class FakeSession:
    """Pass any mix of ORM instances (Document, Chunk, ...) as `objects`; get()/query() match
    by isinstance() against the model class the route code asks for."""

    def __init__(self, objects: list | None = None):
        self._objects: list = list(objects or [])
        self.added: list = []
        self.committed = False
        self._next_id = 1000

    def get(self, model, id_):
        for obj in self._objects:
            if isinstance(obj, model) and obj.id == id_:
                return obj
        return None

    def query(self, model) -> _FakeQuery:
        return _FakeQuery([o for o in self._objects if isinstance(o, model)])

    def add(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = self._next_id
            self._next_id += 1
        self._objects.append(obj)
        self.added.append(obj)

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        self.committed = True
