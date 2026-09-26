"""Add contacts, blocks, bots, room_meta (Phases 41-45).

Revision ID: 0004_contacts_discovery_bots
Revises: 0003_edit_ttl_transcript
Create Date: 2026-09-26
"""
from alembic import op


revision = "0004_contacts_discovery_bots"
down_revision = "0003_edit_ttl_transcript"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            user_id INTEGER NOT NULL,
            contact_user_id INTEGER NOT NULL,
            favourite INTEGER NOT NULL DEFAULT 0,
            nickname TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, contact_user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_contacts_user ON contacts(user_id, favourite DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            blocker_id INTEGER NOT NULL,
            blocked_id INTEGER NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (blocker_id, blocked_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_blocks_blocked ON blocks(blocked_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            name TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            commands TEXT NOT NULL DEFAULT 'help,echo,time',
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_bots_room ON bots(room_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS room_meta (
            room_id TEXT PRIMARY KEY,
            description TEXT,
            tags TEXT,
            published INTEGER NOT NULL DEFAULT 0,
            published_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_room_meta_published ON room_meta(published, published_at DESC)")

    # Add columns to rooms + voice_clips + room_files
    for table, cols in (
        ("rooms", [("description", "TEXT"),
                   ("tags", "TEXT"),
                   ("published_at", "TIMESTAMP")]),
        ("voice_clips", [("room_id", "TEXT")]),
        ("room_files", [("kind", "TEXT NOT NULL DEFAULT 'file'")]),
    ):
        for name, ddl in cols:
            op.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS room_meta")
    op.execute("DROP TABLE IF EXISTS bots")
    op.execute("DROP TABLE IF EXISTS blocks")
    op.execute("DROP TABLE IF EXISTS contacts")
