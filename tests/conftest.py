"""Shared pytest fixtures."""
import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with an isolated SQLite database."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from web.backend.database import init_db
    from web.backend.main import app
    init_db()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
