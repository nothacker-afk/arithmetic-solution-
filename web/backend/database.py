"""Database layer using stdlib sqlite3 (no compilation needed on Termux).

The DB path is read dynamically so tests can override it via the
DB_PATH environment variable.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path




# ---------------------------------------------------------------------
# Backend dispatch (Phase 15)
# ---------------------------------------------------------------------
# When DB_BACKEND=postgres, database_pg provides the same get_db/init_db
# interface. On Termux (default), sqlite3 is used directly below.
import os as _os

if _os.environ.get("DB_BACKEND", "sqlite").lower() == "postgres":
    from .database_pg import get_db, init_db, reset_db  # noqa: F401
    _USE_PG = True
else:
    _USE_PG = False


def get_db_path() -> str:
    """Return the current database path (env-driven)."""
    return os.environ.get("DB_PATH", str(Path.home() / ".arithmetic.db"))


@contextmanager
def _sqlite_get_db():
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

CREATE TABLE IF NOT EXISTS room_files (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    encrypted INTEGER NOT NULL DEFAULT 1,
    uploaded_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_files_room ON room_files(room_id, created_at DESC);

CREATE TABLE IF NOT EXISTS rooms (
    name TEXT PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    password_hash TEXT,
    is_public INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS room_members (
    room_name TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (room_name, user_id),
    FOREIGN KEY (room_name) REFERENCES rooms(name) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_members_user ON room_members(user_id);

CREATE TABLE IF NOT EXISTS room_invites (
    token TEXT PRIMARY KEY,
    room_name TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_name) REFERENCES rooms(name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_invites_room ON room_invites(room_name);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    actor_id INTEGER,
    resource TEXT,
    resource_id TEXT,
    status TEXT NOT NULL DEFAULT 'ok',
    details TEXT,
    ip TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action, created_at DESC);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY,
    theme TEXT NOT NULL DEFAULT 'auto',
    language TEXT NOT NULL DEFAULT 'en',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


def _sqlite_init_db() -> None:
    """Create tables if they don't exist."""
    with get_db() as conn:
        conn.executescript(SCHEMA)


def _sqlite_reset_db() -> None:
    """Drop and recreate all tables (used in tests)."""
    with get_db() as conn:
        conn.executescript("""
            DROP TABLE IF EXISTS calculations;
            DROP TABLE IF EXISTS users;
        """)
        conn.executescript(SCHEMA)

# Aliases for the sqlite backend (used when DB_BACKEND != postgres)
if not _USE_PG:
    get_db = _sqlite_get_db
    init_db = _sqlite_init_db
    reset_db = _sqlite_reset_db
