"""Add emoji packs, guest tokens, room archives.

Revision ID: 0008_emoji_guest_archive
Revises: 0007_groups_templates
Create Date: 2026-09-26
"""
from alembic import op


revision = "0008_emoji_guest_archive"
down_revision = "0007_groups_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS emoji_packs (
            id TEXT PRIMARY KEY,
            room_id TEXT,
            name TEXT NOT NULL,
            created_by INTEGER,
            is_public INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_emoji_packs_room ON emoji_packs(room_id, is_public)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS emoji_pack_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pack_id TEXT NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (pack_id, name)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_emoji_items_pack ON emoji_pack_items(pack_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS guest_access_tokens (
            token TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            created_by INTEGER,
            label TEXT,
            expires_at TIMESTAMP,
            uses_remaining INTEGER,
            use_count INTEGER NOT NULL DEFAULT 0,
            allow_write INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_guest_tokens_room ON guest_access_tokens(room_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS room_archives (
            id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            created_by INTEGER,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            message_count INTEGER NOT NULL DEFAULT 0,
            wiki_count INTEGER NOT NULL DEFAULT 0,
            file_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_archives_room ON room_archives(room_id, created_at DESC)")

    # Add parent_id to group_messages
    op.execute("ALTER TABLE group_messages ADD COLUMN parent_id INTEGER")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS room_archives")
    op.execute("DROP TABLE IF EXISTS guest_access_tokens")
    op.execute("DROP TABLE IF EXISTS emoji_pack_items")
    op.execute("DROP TABLE IF EXISTS emoji_packs")
