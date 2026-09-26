"""Add group DMs and room template tracking.

Revision ID: 0007_groups_templates
Revises: 0006_pins_wiki_vc_events_status
Create Date: 2026-09-26
"""
from alembic import op


revision = "0007_groups_templates"
down_revision = "0006_pins_wiki_vc_events_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS group_threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_message_at TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id)")
    op.execute("""
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_group_messages_thread ON group_messages(group_id, created_at)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS room_template_applied (
            room_id TEXT PRIMARY KEY,
            template_id TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            applied_by INTEGER,
            config TEXT
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS room_template_applied")
    op.execute("DROP TABLE IF EXISTS group_messages")
    op.execute("DROP TABLE IF EXISTS group_members")
    op.execute("DROP TABLE IF EXISTS group_threads")
