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
    # --- Phase 61 — custom emoji packs ---
    """
    CREATE TABLE IF NOT EXISTS emoji_packs (
        id TEXT PRIMARY KEY,
        room_id TEXT,
        name TEXT NOT NULL,
        created_by INTEGER,
        is_public INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_emoji_packs_room ON emoji_packs(room_id, is_public)",

    """
    CREATE TABLE IF NOT EXISTS emoji_pack_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pack_id TEXT NOT NULL,
        name TEXT NOT NULL,
        emoji TEXT,
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (pack_id, name),
        FOREIGN KEY (pack_id) REFERENCES emoji_packs(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_emoji_items_pack ON emoji_pack_items(pack_id)",

    # --- Phase 65 — guest access tokens ---
    """
    CREATE TABLE IF NOT EXISTS guest_access_tokens (
        token TEXT PRIMARY KEY,
        room_id TEXT NOT NULL,
        created_by INTEGER,
        label TEXT,
        expires_at TIMESTAMP,
        uses_remaining INTEGER,
        use_count INTEGER NOT NULL DEFAULT 0,
        allow_write INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_guest_tokens_room ON guest_access_tokens(room_id)",

    # --- Phase 66 — room archives ---
    """
    CREATE TABLE IF NOT EXISTS room_archives (
        id TEXT PRIMARY KEY,
        room_id TEXT NOT NULL,
        created_by INTEGER,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        message_count INTEGER NOT NULL DEFAULT 0,
        wiki_count INTEGER NOT NULL DEFAULT 0,
        file_count INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_archives_room ON room_archives(room_id, created_at DESC)",
    # --- Phase 67 — multi-device sync ---
    """
    CREATE TABLE IF NOT EXISTS device_sync_state (
        user_id INTEGER NOT NULL,
        device_id TEXT NOT NULL,
        label TEXT,
        platform TEXT,
        last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, device_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_device_sync_user ON device_sync_state(user_id, last_seen_at DESC)",

    """
    CREATE TABLE IF NOT EXISTS device_read_state (
        user_id INTEGER NOT NULL,
        device_id TEXT NOT NULL,
        room_id TEXT NOT NULL,
        last_read_message_id INTEGER NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, device_id, room_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_device_read_room ON device_read_state(user_id, room_id)",

    # --- Phase 68 — wiki comments ---
    """
    CREATE TABLE IF NOT EXISTS wiki_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        parent_id INTEGER,
        body TEXT NOT NULL,
        edited_at TIMESTAMP,
        deleted INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_wiki_comments_page ON wiki_comments(page_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_wiki_comments_parent ON wiki_comments(parent_id)",

    # --- Phase 70 — group E2E ---
    """
    CREATE TABLE IF NOT EXISTS group_keys (
        group_id INTEGER PRIMARY KEY,
        salt TEXT NOT NULL,
        key_version INTEGER NOT NULL DEFAULT 1,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES group_threads(id) ON DELETE CASCADE
    )
    """,

    # --- Phase 72 — per-action audit retention ---
    """
    CREATE TABLE IF NOT EXISTS audit_retention_policies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_pattern TEXT NOT NULL UNIQUE,
        retention_days INTEGER NOT NULL,
        created_by INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    # --- Phase 73 — event reminders ---
    """
    CREATE TABLE IF NOT EXISTS event_reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        minutes_before INTEGER NOT NULL DEFAULT 15,
        sent_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (event_id, user_id, minutes_before),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_reminders_due ON event_reminders(sent_at, event_id)",

    # --- Phase 75 — email digests ---
    """
    CREATE TABLE IF NOT EXISTS digest_subscriptions (
        user_id INTEGER PRIMARY KEY,
        frequency TEXT NOT NULL DEFAULT 'weekly',
        enabled INTEGER NOT NULL DEFAULT 1,
        last_sent_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS digest_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'sent',
        details TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_digest_log_user ON digest_log(user_id, sent_at DESC)",

    # --- Phase 76 — advanced RBAC ---
    """
    CREATE TABLE IF NOT EXISTS room_roles (
        room_id TEXT NOT NULL,
        name TEXT NOT NULL,
        permissions TEXT NOT NULL,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (room_id, name),
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_roles_room ON room_roles(room_id)",

    """
    CREATE TABLE IF NOT EXISTS room_role_assignments (
        room_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        role_name TEXT NOT NULL,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        assigned_by INTEGER,
        PRIMARY KEY (room_id, user_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_role_assignments_user ON room_role_assignments(user_id)",

    # --- Phase 74 — bulk op audit ---
    """
    CREATE TABLE IF NOT EXISTS bulk_operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id TEXT NOT NULL,
        action TEXT NOT NULL,
        actor_id INTEGER NOT NULL,
        target_count INTEGER NOT NULL,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_bulk_ops_room ON bulk_operations(room_id, created_at DESC)",
    # --- Phase 79 — VAPID web push subscriptions ---
    """
    CREATE TABLE IF NOT EXISTS web_push_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        endpoint TEXT NOT NULL UNIQUE,
        p256dh TEXT NOT NULL,
        auth TEXT NOT NULL,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_used_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_wps_user ON web_push_subscriptions(user_id, last_used_at DESC)",

    # --- Phase 81 — room themes ---
    """
    CREATE TABLE IF NOT EXISTS room_themes (
        room_id TEXT PRIMARY KEY,
        accent TEXT,
        accent_2 TEXT,
        banner_url TEXT,
        emoji TEXT,
        background TEXT,
        font_family TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_by INTEGER,
        FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
    )
    """,
]

EXTRA_COLUMNS = {
    "group_messages": [
        ("parent_id", "INTEGER"),
    ],
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


# =====================================================================
# Phase 80 — Wiki full-text search (FTS5)
# =====================================================================
WIKI_FTS_AVAILABLE = None  # cached capability check

    # Phase 80 — wiki FTS (idempotent rebuild)
    ensure_wiki_fts(conn)


def _wiki_fts_supported(conn) -> bool:
    """Check if FTS5 is available in this SQLite build."""
    global WIKI_FTS_AVAILABLE
    if WIKI_FTS_AVAILABLE is not None:
        return WIKI_FTS_AVAILABLE
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS __fts_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS __fts_probe")
        WIKI_FTS_AVAILABLE = True
    except Exception:
        WIKI_FTS_AVAILABLE = False
    return WIKI_FTS_AVAILABLE


def ensure_wiki_fts(conn) -> bool:
    """Create wiki_fts + triggers, then rebuild from wiki_pages.

    Safe to call repeatedly. Returns True if FTS5 is active after this call.
    """
    if not _wiki_fts_supported(conn):
        return False

    try:
        # 1. Create the FTS5 table
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
                title, body, slug UNINDEXED,
                content='wiki_pages', content_rowid='rowid',
                tokenize='unicode61'
            )
        """)

        # 2. Create sync triggers
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS wiki_fts_ai
            AFTER INSERT ON wiki_pages BEGIN
                INSERT INTO wiki_fts(rowid, title, body, slug)
                VALUES (new.rowid, new.title, new.body, new.slug);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS wiki_fts_ad
            AFTER DELETE ON wiki_pages BEGIN
                INSERT INTO wiki_fts(wiki_fts, rowid, title, body, slug)
                VALUES ('delete', old.rowid, old.title, old.body, old.slug);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS wiki_fts_au
            AFTER UPDATE ON wiki_pages BEGIN
                INSERT INTO wiki_fts(wiki_fts, rowid, title, body, slug)
                VALUES ('delete', old.rowid, old.title, old.body, old.slug);
                INSERT INTO wiki_fts(rowid, title, body, slug)
                VALUES (new.rowid, new.title, new.body, new.slug);
            END
        """)

        # 3. Rebuild the index from the content table.
        #    FTS5's special 'rebuild' command re-indexes everything from
        #    wiki_pages, which is exactly what we want — idempotent, fast.
        conn.execute("INSERT INTO wiki_fts(wiki_fts) VALUES('rebuild')")
        return True
    except Exception as e:
        import logging
        logging.getLogger("web.schema").warning("wiki_fts setup failed: %s", e)
        return False
