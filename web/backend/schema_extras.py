"""Schema extensions introduced after the initial SCHEMA (Phase 41+).

`ensure_extras(conn)` is idempotent. It is called from database.init_db()
so fresh test DBs and existing DBs both get the new tables/columns.
"""
from .logging_config import get_logger

log = get_logger("web.schema")

# Tables added after the initial schema (idempotent CREATE IF NOT EXISTS)
EXTRA_TABLES = [
    # Phase 41 — contacts + blocks
    """
    CREATE TABLE IF NOT EXISTS contacts (
        user_id INTEGER NOT NULL,
        contact_user_id INTEGER NOT NULL,
        favourite INTEGER NOT NULL DEFAULT 0,
        nickname TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, contact_user_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (contact_user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_contacts_user ON contacts(user_id, favourite DESC)",

    """
    CREATE TABLE IF NOT EXISTS blocks (
        blocker_id INTEGER NOT NULL,
        blocked_id INTEGER NOT NULL,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (blocker_id, blocked_id),
        FOREIGN KEY (blocker_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (blocked_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_blocks_blocked ON blocks(blocked_id)",

    # Phase 43 — bots
    """
    CREATE TABLE IF NOT EXISTS bots (
        id TEXT PRIMARY KEY,
        room_id TEXT NOT NULL,
        name TEXT NOT NULL,
        token_hash TEXT NOT NULL,
        commands TEXT NOT NULL DEFAULT 'help,echo,time',
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_bots_room ON bots(room_id)",

    # Phase 42 — room discovery metadata
    """
    CREATE TABLE IF NOT EXISTS room_meta (
        room_id TEXT PRIMARY KEY,
        description TEXT,
        tags TEXT,
        published INTEGER NOT NULL DEFAULT 0,
        published_at TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_room_meta_published ON room_meta(published, published_at DESC)",
    # Phase 46 — scheduled messages
    """
    CREATE TABLE IF NOT EXISTS scheduled_messages (
        id TEXT PRIMARY KEY,
        room_id TEXT NOT NULL,
        sender_id INTEGER,
        sender_username TEXT NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        encrypted INTEGER NOT NULL DEFAULT 0,
        kind TEXT NOT NULL DEFAULT 'text',
        attachment_id TEXT,
        send_at TIMESTAMP NOT NULL,
        sent INTEGER NOT NULL DEFAULT 0,
        sent_message_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sched_due ON scheduled_messages(sent, send_at)",
    "CREATE INDEX IF NOT EXISTS idx_sched_sender ON scheduled_messages(sender_id, created_at DESC)",

    # Phase 47 — room read receipts
    """
    CREATE TABLE IF NOT EXISTS room_read_state (
        room_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        last_read_message_id INTEGER NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (room_id, user_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_room_read ON room_read_state(room_id, last_read_message_id)",

    # Phase 50 — offline action log (per-user queue mirror)
    """
    CREATE TABLE IF NOT EXISTS offline_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        client_id TEXT NOT NULL,
        method TEXT NOT NULL,
        path TEXT NOT NULL,
        body TEXT,
        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (user_id, client_id)
    )
    """,
]

# Columns to add to existing tables
EXTRA_COLUMNS = {
    "rooms": [
        ("description", "TEXT"),
        ("tags", "TEXT"),
        ("published_at", "TIMESTAMP"),
    ],
    "voice_clips": [
        ("room_id", "TEXT"),
    ],
    "room_files": [
        ("kind", "TEXT NOT NULL DEFAULT 'file'"),
    ],
}


def ensure_extras(conn) -> None:
    """Create new tables and add new columns. Idempotent."""
    for stmt in EXTRA_TABLES:
        try:
            conn.execute(stmt)
        except Exception as e:
            log.warning("extra table failed (%s): %s", stmt.split()[5], e)

    _apply_extra_tables_2(conn)

    for table, columns in EXTRA_COLUMNS.items():
        try:
            existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if not existing:
                continue
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
        except Exception as e:
            log.warning("extra column on %s failed: %s", table, e)
