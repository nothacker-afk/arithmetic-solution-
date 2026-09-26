"""Shared pytest fixtures with full DB initialization per test."""
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
    """Isolated SQLite DB, fully initialized schema per test."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))

    from web.backend import main as backend_main
    from web.backend import database

    # init_db runs SCHEMA + _ensure_columns
    database.init_db()

    # Belt & braces: explicit column check
    try:
        with database.get_db() as conn:
            database._ensure_columns(conn)
    except Exception:
        pass

    try:
        from web.backend import search as search_mod
        search_mod.init_fts()
    except Exception:
        pass

    backend_main._db_initialized = True
    backend_main.app.config["TESTING"] = True

    try:
        from web.backend import realtime
        realtime.reset_state()
    except Exception:
        pass

    with backend_main.app.test_client() as c:
        yield c
