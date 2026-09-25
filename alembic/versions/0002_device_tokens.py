"""Add device_tokens for push notifications.

Revision ID: 0002_device_tokens
Revises: 0001_initial
Create Date: 2026-09-26
"""
from alembic import op


revision = "0002_device_tokens"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS device_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL DEFAULT 'unknown',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_device_user ON device_tokens(user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS device_tokens")
