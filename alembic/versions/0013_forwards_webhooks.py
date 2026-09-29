"""Add message_forwards, webhooks, webhook_deliveries.

Revision ID: 0013_forwards_webhooks
Revises: 0012_dm_threads_translations_retention
Create Date: 2026-09-29
"""
from alembic import op


revision = "0013_forwards_webhooks"
down_revision = "0012_dm_threads_translations_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS message_forwards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_kind TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            source_room TEXT,
            dest_kind TEXT NOT NULL,
            dest_id INTEGER NOT NULL,
            dest_room TEXT,
            new_message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_forwards_user ON message_forwards(user_id, created_at DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS webhooks (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            secret TEXT NOT NULL,
            events TEXT NOT NULL,
            description TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_delivery_at TIMESTAMP,
            last_status_code INTEGER,
            failure_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_user ON webhooks(user_id, enabled)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            webhook_id TEXT NOT NULL,
            event TEXT NOT NULL,
            status_code INTEGER,
            error TEXT,
            duration_ms INTEGER,
            attempt INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_webhook_deliv ON webhook_deliveries(webhook_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS webhook_deliveries")
    op.execute("DROP TABLE IF EXISTS webhooks")
    op.execute("DROP TABLE IF EXISTS message_forwards")
