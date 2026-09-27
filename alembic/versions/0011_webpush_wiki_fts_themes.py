"""Add web push subscriptions, wiki FTS, room themes.

Revision ID: 0011_webpush_wiki_fts_themes
Revises: 0010_reminders_bulk_digest_rbac
Create Date: 2026-09-26
"""
from alembic import op


revision = "0011_webpush_wiki_fts_themes"
down_revision = "0010_reminders_bulk_digest_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS web_push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_wps_user ON web_push_subscriptions(user_id, last_used_at DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS room_themes (
            room_id TEXT PRIMARY KEY,
            accent TEXT,
            accent_2 TEXT,
            banner_url TEXT,
            emoji TEXT,
            background TEXT,
            font_family TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER
        )
    """)

    # Wiki FTS — best-effort (may fail if FTS5 not compiled)
    try:
        op.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
                title, body, slug UNINDEXED,
                content='wiki_pages', content_rowid='rowid',
                tokenize='unicode61'
            )
        """)
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS wiki_fts_ai AFTER INSERT ON wiki_pages BEGIN
                INSERT INTO wiki_fts(rowid, title, body, slug)
                VALUES (new.rowid, new.title, new.body, new.slug);
            END
        """)
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS wiki_fts_ad AFTER DELETE ON wiki_pages BEGIN
                INSERT INTO wiki_fts(wiki_fts, rowid, title, body, slug)
                VALUES ('delete', old.rowid, old.title, old.body, old.slug);
            END
        """)
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS wiki_fts_au AFTER UPDATE ON wiki_pages BEGIN
                INSERT INTO wiki_fts(wiki_fts, rowid, title, body, slug)
                VALUES ('delete', old.rowid, old.title, old.body, old.slug);
                INSERT INTO wiki_fts(rowid, title, body, slug)
                VALUES (new.rowid, new.title, new.body, new.slug);
            END
        """)
    except Exception:
        pass


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS room_themes")
    op.execute("DROP TABLE IF EXISTS web_push_subscriptions")
