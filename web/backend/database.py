"""Database layer using stdlib sqlite3 (no compilation needed on Termux).

The DB path is read dynamically so tests can override it via the
DB_PATH environment variable.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def get_db_path() -> str:
    """Return the current database path (env-driven)."""
    return os.environ.get("DB_PATH", str(Path.home() / ".arithmetic.db"))


@contextmanager
def get_db():
    """Context manager yielding a sqlite3 connection."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS calculations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    expression TEXT NOT NULL,
    result TEXT NOT NULL,
    operation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_calc_user ON calculations(user_id);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    username TEXT NOT NULL,
    body TEXT NOT NULL,
    encrypted INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_room ON chat_messages(room_id, id);
"""


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_db() as conn:
        conn.executescript(SCHEMA)


def reset_db() -> None:
    """Drop and recreate all tables (used in tests)."""
    with get_db() as conn:
        conn.executescript("""
            DROP TABLE IF EXISTS calculations;
            DROP TABLE IF EXISTS users;
        """)
        conn.executescript(SCHEMA)
