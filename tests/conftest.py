"""Shared pytest fixtures with DB + FTS + rate-limit isolation per test."""
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
    """Flask test client with an isolated SQLite DB + FTS initialized."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))

    from web.backend import main as backend_main
    from web.backend import database
    from web.backend import search as search_mod

    database.init_db()
    try:
        search_mod.init_fts()
    except Exception:
        pass  # FTS unavailable — search falls back to LIKE

    backend_main._db_initialized = True
    backend_main.app.config["TESTING"] = True

    # Reset WebSocket room state too
    try:
        from web.backend import realtime
        realtime.reset_state()
    except Exception:
        pass

    with backend_main.app.test_client() as c:
        yield c
