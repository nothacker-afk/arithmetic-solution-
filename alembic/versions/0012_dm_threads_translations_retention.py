"""Add DM threads, translation cache, room retention overrides.

Revision ID: 0012_dm_threads_translations_retention
Revises: 0011_webpush_wiki_fts_themes
Create Date: 2026-09-28
"""
from alembic import op


revision = "0012_dm_threads_translations_retention"
down_revision = "0011_webpush_wiki_fts_themes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 82 — dm_messages.parent_id
    op.execute("ALTER TABLE dm_messages ADD COLUMN parent_id INTEGER")

    # Phase 83 — message_translations
    op.execute("""
        CREATE TABLE IF NOT EXISTS message_translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message_kind TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            target_lang TEXT NOT NULL,
            source_lang TEXT,
            translated_body TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'openai',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, message_kind, message_id, target_lang)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_translations_user ON message_translations(user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_translations_msg ON message_translations(message_kind, message_id)")

    # Phase 84 — room_retention_overrides
    op.execute("""
        CREATE TABLE IF NOT EXISTS room_retention_overrides (
            room_id TEXT PRIMARY KEY,
            message_days INTEGER,
            chat_days INTEGER,
            audit_days INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS room_retention_overrides")
    op.execute("DROP TABLE IF EXISTS message_translations")
