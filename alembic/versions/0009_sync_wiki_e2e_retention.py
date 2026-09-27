"""Add device sync, wiki comments, group keys, audit retention.

Revision ID: 0009_sync_wiki_e2e_retention
Revises: 0008_emoji_guest_archive
Create Date: 2026-09-26
"""
from alembic import op


revision = "0009_sync_wiki_e2e_retention"
down_revision = "0008_emoji_guest_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS device_sync_state (
            user_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            label TEXT,
            platform TEXT,
            last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, device_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_device_sync_user ON device_sync_state(user_id, last_seen_at DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS device_read_state (
            user_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            room_id TEXT NOT NULL,
            last_read_message_id INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, device_id, room_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_device_read_room ON device_read_state(user_id, room_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS wiki_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            parent_id INTEGER,
            body TEXT NOT NULL,
            edited_at TIMESTAMP,
            deleted INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_wiki_comments_page ON wiki_comments(page_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_wiki_comments_parent ON wiki_comments(parent_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS group_keys (
            group_id INTEGER PRIMARY KEY,
            salt TEXT NOT NULL,
            key_version INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_retention_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_pattern TEXT NOT NULL UNIQUE,
            retention_days INTEGER NOT NULL,
            created_by INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_retention_policies")
    op.execute("DROP TABLE IF EXISTS group_keys")
    op.execute("DROP TABLE IF EXISTS wiki_comments")
    op.execute("DROP TABLE IF EXISTS device_read_state")
    op.execute("DROP TABLE IF EXISTS device_sync_state")
