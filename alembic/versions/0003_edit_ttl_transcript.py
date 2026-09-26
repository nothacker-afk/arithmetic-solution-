"""Add edit history, tombstones, TTLs, transcripts.

Revision ID: 0003_edit_ttl_transcript
Revises: 0002_device_tokens
Create Date: 2026-09-26
"""
from alembic import op


revision = "0003_edit_ttl_transcript"
down_revision = "0002_device_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # message_edits
    op.execute("""
        CREATE TABLE IF NOT EXISTS message_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_kind TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            old_body TEXT NOT NULL,
            edited_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_edits_msg ON message_edits(message_kind, message_id)")

    # room_ttls + thread_ttls
    op.execute("""
        CREATE TABLE IF NOT EXISTS room_ttls (
            room_id TEXT PRIMARY KEY,
            ttl_seconds INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS thread_ttls (
            thread_id INTEGER PRIMARY KEY,
            ttl_seconds INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER
        )
    """)

    # New columns on chat_messages + dm_messages + voice_clips
    for table, cols in (
        ("chat_messages", [("edited_at", "TIMESTAMP"),
                            ("deleted", "INTEGER NOT NULL DEFAULT 0"),
                            ("expires_at", "TIMESTAMP")]),
        ("dm_messages",   [("edited_at", "TIMESTAMP"),
                            ("deleted", "INTEGER NOT NULL DEFAULT 0"),
                            ("expires_at", "TIMESTAMP")]),
        ("voice_clips",   [("transcript", "TEXT"), ("transcript_lang", "TEXT")]),
    ):
        for name, ddl in cols:
            op.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS message_edits")
    op.execute("DROP TABLE IF EXISTS room_ttls")
    op.execute("DROP TABLE IF EXISTS thread_ttls")
