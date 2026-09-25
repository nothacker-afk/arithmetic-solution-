"""PostgreSQL adapter (Phase 15).

Drop-in replacement for database.py when DB_BACKEND=postgres. Uses
SQLAlchemy Core to execute the same SQL our sqlite3 code uses, with
'?' placeholders translated to SQLAlchemy named params.

To activate:
    export DB_BACKEND=postgres
    export DATABASE_URL=postgresql+psycopg://user:pass@host/db
    pip install psycopg[binary] sqlalchemy

On Termux, stick with the default sqlite backend.
"""
import os
import re
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection


_ENGINE = None


def _get_engine():
    global _ENGINE
    if _ENGINE is None:
        url = os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://arith:arith@localhost:5432/arith",
        )
        _ENGINE = create_engine(url, pool_pre_ping=True, future=True)
    return _ENGINE


def _translate(sql: str) -> str:
    """Replace '?' placeholders with SQLAlchemy named params :p0, :p1, ..."""
    parts = sql.split("?")
    out = parts[0]
    for i, p in enumerate(parts[1:]):
        out += f":p{i}" + p
    return out


def _bind(params):
    if params is None:
        return {}
    if isinstance(params, dict):
        return params
    return {f"p{i}": v for i, v in enumerate(params)}


class _Cursor:
    def __init__(self, result):
        self._r = result
        self.lastrowid = None
        try:
            self.lastrowid = result.lastrowid
        except Exception:
            pass

    def fetchone(self):
        row = self._r.fetchone()
        return dict(row._mapping) if row else None

    def fetchall(self):
        return [dict(r._mapping) for r in self._r.fetchall()]

    @property
    def rowcount(self):
        return self._r.rowcount


class _Conn:
    def __init__(self, conn: Connection):
        self._conn = conn

    def execute(self, sql: str, params=None):
        stmt = text(_translate(sql))
        result = self._conn.execute(stmt, _bind(params))
        return _Cursor(result)

    def executescript(self, script: str):
        for stmt in re.split(r";\s*\n", script):
            stmt = stmt.strip()
            if stmt:
                self._conn.execute(text(stmt))

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        pass


@contextmanager
def get_db():
    conn = _get_engine().connect()
    wrapper = _Conn(conn)
    try:
        yield wrapper
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    from .database import SCHEMA
    with get_db() as conn:
        conn.executescript(SCHEMA)


def reset_db() -> None:
    with get_db() as conn:
        conn.executescript("""
            DROP TABLE IF EXISTS account_backups;
            DROP TABLE IF EXISTS audit_log;
            DROP TABLE IF EXISTS user_preferences;
            DROP TABLE IF EXISTS room_invites;
            DROP TABLE IF EXISTS room_members;
            DROP TABLE IF EXISTS rooms;
            DROP TABLE IF EXISTS room_files;
            DROP TABLE IF EXISTS chat_messages;
            DROP TABLE IF EXISTS calculations;
            DROP TABLE IF EXISTS users;
        """)
    init_db()
