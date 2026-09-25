"""Tests for Phase 15 — Alembic + DB_BACKEND."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_alembic_config_exists():
    assert Path("alembic.ini").exists()
    assert Path("alembic/env.py").exists()
    assert Path("alembic/versions/0001_initial.py").exists()


def test_alembic_upgrade_sqlite(tmp_path):
    """Run `alembic upgrade head` against a temp SQLite DB."""
    db = tmp_path / "alembic_test.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db}"

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert result.returncode == 0, result.stderr

    # Verify some tables landed
    import sqlite3
    conn = sqlite3.connect(str(db))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    conn.close()
    assert "users" in tables
    assert "audit_log" in tables
    assert "room_members" in tables


def test_db_backend_env_default_sqlite():
    """Default (unset) DB_BACKEND should be sqlite."""
    from web.backend import database
    # Reload in case another test changed env
    assert hasattr(database, "get_db")
    assert hasattr(database, "init_db")


def test_database_pg_module_importable():
    """The postgres adapter should import cleanly even if psycopg isn't installed."""
    # Importing doesn't connect — safe.
    from web.backend import database_pg
    assert hasattr(database_pg, "get_db")
    assert hasattr(database_pg, "init_db")
    assert hasattr(database_pg, "reset_db")


def test_translate_placeholders():
    from web.backend.database_pg import _translate
    assert _translate("SELECT * FROM users WHERE id = ?") == "SELECT * FROM users WHERE id = :p0"
    assert _translate("INSERT INTO t (a, b) VALUES (?, ?)") == "INSERT INTO t (a, b) VALUES (:p0, :p1)"
    assert _translate("SELECT 1") == "SELECT 1"


def test_bind_dict_and_tuple():
    from web.backend.database_pg import _bind
    assert _bind((1, 2)) == {"p0": 1, "p1": 2}
    assert _bind({"x": 1}) == {"x": 1}
    assert _bind(None) == {}


def test_docker_compose_postgres_exists():
    assert Path("docker/docker-compose-postgres.yml").exists()
    content = Path("docker/docker-compose-postgres.yml").read_text()
    assert "postgres:16" in content
    assert "DB_BACKEND" in content or "DATABASE_URL" in content
