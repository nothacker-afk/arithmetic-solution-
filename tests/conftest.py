"""Shared pytest fixtures with proper DB isolation per test."""
import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with an isolated SQLite database per test.

    Resets the lazy-init flag on the app so each test gets a fresh DB.
    """
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))

    from web.backend import main as backend_main
    from web.backend import database

    # Force a clean DB for this test
    database.init_db()

    # Reset the lazy-init flag so before_request runs init_db() again
    backend_main._db_initialized = True  # we already called it above

    backend_main.app.config["TESTING"] = True
    with backend_main.app.test_client() as c:
        yield c
