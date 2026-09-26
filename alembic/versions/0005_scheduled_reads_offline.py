"""Add scheduled_messages, room_read_state, offline_actions.

Revision ID: 0005_scheduled_reads_offline
Revises: 0004_contacts_discovery_bots
Create Date: 2026-09-26
"""
from alembic import op


revision = "0005_scheduled_reads_offline"
down_revision = "0004_contacts_discovery_bots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
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
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sched_due ON scheduled_messages(sent, send_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sched_sender ON scheduled_messages(sender_id, created_at DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS room_read_state (
            room_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            last_read_message_id INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (room_id, user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_room_read ON room_read_state(room_id, last_read_message_id)")

    op.execute("""
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
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS offline_actions")
    op.execute("DROP TABLE IF EXISTS room_read_state")
    op.execute("DROP TABLE IF EXISTS scheduled_messages")
