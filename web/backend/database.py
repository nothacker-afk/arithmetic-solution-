"""SQLite layer + DB_BACKEND dispatch.

`init_db()` is idempotent and self-healing: it runs the full SCHEMA
plus an explicit `_ensure_extra_tables()` step that creates any tables
introduced after the initial schema, so upgrades never miss a table.
"""
import os as _os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_USE_PG = _os.environ.get("DB_BACKEND", "sqlite").lower() == "postgres"


def get_db_path() -> str:
    return _os.environ.get("DB_PATH", str(Path.home() / ".arithmetic.db"))


@contextmanager
def _sqlite_get_db():
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
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY,
    theme TEXT NOT NULL DEFAULT 'auto',
    language TEXT NOT NULL DEFAULT 'en',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
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
"""


# ---------------------------------------------------------------------
# Tables added after the original schema go here (idempotent).
# ---------------------------------------------------------------------
EXTRA_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS account_backups (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        label TEXT,
        size_bytes INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_backups_user ON account_backups(user_id, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS device_tokens (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        platform TEXT NOT NULL DEFAULT 'unknown',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_device_user ON device_tokens(user_id)",
    """
    CREATE TABLE IF NOT EXISTS passkeys (
        credential_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        public_key TEXT NOT NULL,
        sign_count INTEGER NOT NULL DEFAULT 0,
        name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_used_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_passkeys_user ON passkeys(user_id)",
    """
    CREATE TABLE IF NOT EXISTS passkey_challenges (
        user_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        challenge TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, kind)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dm_threads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_a INTEGER NOT NULL,
        user_b INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_message_at TIMESTAMP,
        UNIQUE(user_a, user_b),
        FOREIGN KEY (user_a) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (user_b) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_dm_threads_a ON dm_threads(user_a, last_message_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_dm_threads_b ON dm_threads(user_b, last_message_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS dm_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        encrypted INTEGER NOT NULL DEFAULT 1,
        read_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (thread_id) REFERENCES dm_threads(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_dm_messages_thread ON dm_messages(thread_id, created_at)",

]


def _ensure_extra_tables(conn) -> None:
    """Run EXTRA_TABLES against the given connection."""
    for stmt in EXTRA_TABLES:
        conn.execute(stmt)


def _sqlite_init_db():
    with _sqlite_get_db() as conn:
        conn.executescript(SCHEMA)
        _ensure_extra_tables(conn)


def _sqlite_reset_db():
    with _sqlite_get_db() as conn:
        for t in ("account_backups", "audit_log", "user_preferences",
                  "room_invites", "room_members", "rooms", "room_files",
                  "chat_messages", "calculations", "users"):
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.executescript(SCHEMA)
        _ensure_extra_tables(conn)


if _USE_PG:
    from .database_pg import get_db, init_db, reset_db  # noqa: F401
else:
    get_db = _sqlite_get_db
    init_db = _sqlite_init_db
    reset_db = _sqlite_reset_db
