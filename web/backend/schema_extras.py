"""Schema extensions introduced after the initial SCHEMA.

`ensure_extras(conn)` is idempotent. Called from database.init_db() so
fresh test DBs and existing DBs both get the new tables/columns.

All tables added after the initial SCHEMA live here — never patch the
main SCHEMA. That way migrations are simple: add to EXTRA_TABLES.
"""
from .logging_config import get_logger

log = get_logger("web.schema")


EXTRA_TABLES = [
    # --- Phase 41 — contacts + blocks ---
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

    # --- Phase 42 — room discovery metadata ---
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

    # --- Phase 43 — bots ---
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

    # --- Phase 46 — scheduled messages ---
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

    # --- Phase 47 — room read receipts ---
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

    # --- Phase 50 — offline action log ---
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

    # --- Phase 51 — pinned messages ---
    """
    CREATE TABLE IF NOT EXISTS pinned_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id TEXT NOT NULL,
        message_id INTEGER NOT NULL,
        pinned_by INTEGER NOT NULL,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (room_id, message_id),
        FOREIGN KEY (pinned_by) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pins_room ON pinned_messages(room_id, created_at DESC)",

    # --- Phase 52 — room wiki ---
    """
    CREATE TABLE IF NOT EXISTS wiki_pages (
        id TEXT PRIMARY KEY,
        room_id TEXT NOT NULL,
        title TEXT NOT NULL,
        slug TEXT NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        created_by INTEGER,
        updated_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (room_id, slug)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_wiki_room ON wiki_pages(room_id, updated_at DESC)",

    # --- Phase 53 — voice channel presence ---
    """
    CREATE TABLE IF NOT EXISTS voice_channel_presence (
        room_id TEXT NOT NULL,
        channel TEXT NOT NULL DEFAULT 'main',
        user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        muted INTEGER NOT NULL DEFAULT 0,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_ping TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (room_id, channel, user_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_vc_room ON voice_channel_presence(room_id, channel)",

    # --- Phase 54 — room events ---
    """
    CREATE TABLE IF NOT EXISTS room_events (
        id TEXT PRIMARY KEY,
        room_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        starts_at TIMESTAMP NOT NULL,
        ends_at TIMESTAMP,
        all_day INTEGER NOT NULL DEFAULT 0,
        location TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_events_room ON room_events(room_id, starts_at)",
    "CREATE INDEX IF NOT EXISTS idx_events_when ON room_events(starts_at)",

    """
    CREATE TABLE IF NOT EXISTS room_event_rsvps (
        event_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'going',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (event_id, user_id),
        FOREIGN KEY (event_id) REFERENCES room_events(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,

    # --- Phase 55 — user status ---
    """
    CREATE TABLE IF NOT EXISTS user_status (
        user_id INTEGER PRIMARY KEY,
        state TEXT NOT NULL DEFAULT 'available',
        emoji TEXT,
        message TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    # --- Phase 56 — group DMs ---
    """
    CREATE TABLE IF NOT EXISTS group_threads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_message_at TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS group_members (
        group_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'member',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (group_id, user_id),
        FOREIGN KEY (group_id) REFERENCES group_threads(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id)",
    """
    CREATE TABLE IF NOT EXISTS group_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        encrypted INTEGER NOT NULL DEFAULT 1,
        kind TEXT NOT NULL DEFAULT 'text',
        attachment_id TEXT,
        edited_at TIMESTAMP,
        deleted INTEGER NOT NULL DEFAULT 0,
        read_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES group_threads(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_group_messages_thread ON group_messages(group_id, created_at)",

    # --- Phase 59 — room templates ---
    """
    CREATE TABLE IF NOT EXISTS room_template_applied (
        room_id TEXT PRIMARY KEY,
        template_id TEXT NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        applied_by INTEGER,
        config TEXT
    )
    """,
]

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
            head = stmt.strip().split()[:6]
            log.warning("extra table failed (%s): %s", " ".join(head), e)

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
