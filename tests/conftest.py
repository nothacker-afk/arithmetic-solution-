"""Shared pytest fixtures with proper DB + rate-limit isolation per test."""
import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset rate limiter state before every test.

    The rate limiter uses module-level storage keyed by client IP. All tests
    share the same test-client IP, so without a reset, later tests would
    hit HTTP 429.
    """
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
    """Reset in-memory metrics before every test."""
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
    """Flask test client with an isolated SQLite database per test."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))

    from web.backend import main as backend_main
    from web.backend import database

    database.init_db()
    backend_main._db_initialized = True

    backend_main.app.config["TESTING"] = True
    with backend_main.app.test_client() as c:
        yield c
