"""Add event reminders, bulk ops log, digest subs, RBAC.

Revision ID: 0010_reminders_bulk_digest_rbac
Revises: 0009_sync_wiki_e2e_retention
Create Date: 2026-09-26
"""
from alembic import op


revision = "0010_reminders_bulk_digest_rbac"
down_revision = "0009_sync_wiki_e2e_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS event_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            minutes_before INTEGER NOT NULL DEFAULT 15,
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (event_id, user_id, minutes_before)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_reminders_due ON event_reminders(sent_at, event_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS digest_subscriptions (
            user_id INTEGER PRIMARY KEY,
            frequency TEXT NOT NULL DEFAULT 'weekly',
            enabled INTEGER NOT NULL DEFAULT 1,
            last_sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS digest_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'sent',
            details TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_digest_log_user ON digest_log(user_id, sent_at DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS room_roles (
            room_id TEXT NOT NULL,
            name TEXT NOT NULL,
            permissions TEXT NOT NULL,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (room_id, name)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_roles_room ON room_roles(room_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS room_role_assignments (
            room_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            role_name TEXT NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assigned_by INTEGER,
            PRIMARY KEY (room_id, user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_role_assignments_user ON room_role_assignments(user_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS bulk_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            action TEXT NOT NULL,
            actor_id INTEGER NOT NULL,
            target_count INTEGER NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_bulk_ops_room ON bulk_operations(room_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bulk_operations")
    op.execute("DROP TABLE IF EXISTS room_role_assignments")
    op.execute("DROP TABLE IF EXISTS room_roles")
    op.execute("DROP TABLE IF EXISTS digest_log")
    op.execute("DROP TABLE IF EXISTS digest_subscriptions")
    op.execute("DROP TABLE IF EXISTS event_reminders")
