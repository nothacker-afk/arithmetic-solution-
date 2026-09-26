"""Add pins, wiki, voice channel presence, events, status.

Revision ID: 0006_pins_wiki_vc_events_status
Revises: 0005_scheduled_reads_offline
Create Date: 2026-09-26
"""
from alembic import op


revision = "0006_pins_wiki_vc_events_status"
down_revision = "0005_scheduled_reads_offline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS pinned_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            pinned_by INTEGER NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (room_id, message_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pins_room ON pinned_messages(room_id, created_at DESC)")

    op.execute("""
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
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_wiki_room ON wiki_pages(room_id, updated_at DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS voice_channel_presence (
            room_id TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'main',
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            muted INTEGER NOT NULL DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_ping TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (room_id, channel, user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_vc_room ON voice_channel_presence(room_id, channel)")

    op.execute("""
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
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_room ON room_events(room_id, starts_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_when ON room_events(starts_at)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS room_event_rsvps (
            event_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'going',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (event_id, user_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS user_status (
            user_id INTEGER PRIMARY KEY,
            state TEXT NOT NULL DEFAULT 'available',
            emoji TEXT,
            message TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_status")
    op.execute("DROP TABLE IF EXISTS room_event_rsvps")
    op.execute("DROP TABLE IF EXISTS room_events")
    op.execute("DROP TABLE IF EXISTS voice_channel_presence")
    op.execute("DROP TABLE IF EXISTS wiki_pages")
    op.execute("DROP TABLE IF EXISTS pinned_messages")
