"""Shared pytest fixtures with DB + FTS + rate-limit isolation per test."""
import os

# Speed + isolation defaults applied before any app import
os.environ.setdefault("FAST_HASH", "1")
os.environ.setdefault("RETENTION_ENABLED", "0")
os.environ.setdefault("BACKGROUND_INTERVAL_SECONDS", "9999")
os.environ.setdefault("SCHEDULER_INTERVAL_SECONDS", "9999")

import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    try:
        from web.backend.rate_limit import reset as rl_reset
        rl_reset()
    except Exception:
        pass
    yield
    try:
        from web.backend.rate_limit import reset as rl_reset
        rl_reset()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _reset_metrics():
    try:
        from web.backend.middleware import METRICS
        METRICS.reset()
    except Exception:
        pass
    yield
    try:
        from web.backend.middleware import METRICS
        METRICS.reset()
    except Exception:
        pass


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Isolated SQLite DB with full schema per test."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))

    from web.backend import main as backend_main
    from web.backend import database

    # 1. Base schema
    database.init_db()

    # 2. Extra tables + columns + wiki FTS
    try:
        from web.backend.schema_extras import ensure_extras
        with database.get_db() as conn:
            ensure_extras(conn)
    except Exception:
        pass

    # 3. Standalone FTS for chat search
    try:
        from web.backend import search as search_mod
        search_mod.init_fts()
    except Exception:
        pass

    backend_main._db_initialized = True
    backend_main.app.config["TESTING"] = True

    # 4. Reset WebSocket room state
    try:
        from web.backend import realtime
        realtime.reset_state()
    except Exception:
        pass

    with backend_main.app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _ensure_db_ready(tmp_path, monkeypatch):
    """Ensure the DB is initialized before every test.

    Prevents crashes when a test calls into a module that touches the
    DB without using the `client` fixture. Sets a fresh per-test DB
    path and runs init_db + ensure_extras + search FTS init.
    """
    # Only set a fresh DB path if not already set by a test.
    if not os.environ.get("DB_PATH") or os.environ.get("DB_PATH") in ("", ":memory:"):
        monkeypatch.setenv("DB_PATH", str(tmp_path / "auto-test.db"))

    from web.backend import database
    try:
        database.init_db()
    except Exception:
        pass

    try:
        from web.backend.schema_extras import ensure_extras
        with database.get_db() as conn:
            ensure_extras(conn)
    except Exception:
        pass

    try:
        from web.backend import search as search_mod
        search_mod.init_fts()
    except Exception:
        pass

    yield
