"""Full-text search across calculations and chat (Phase 26).

Uses SQLite FTS5 virtual tables with triggers to stay in sync. If the
SQLite build doesn't have FTS5, falls back to LIKE-based search.
"""
import os
from flask import Blueprint, request, jsonify, g

from .auth import require_auth
from .database import get_db
from .rate_limit import rate_limit
from .logging_config import get_logger

log = get_logger("web.search")

search_bp = Blueprint("search", __name__, url_prefix="/api/search")

_FTS_AVAILABLE = None  # tri-state: None=unknown, True/False


def fts_available() -> bool:
    """Detect FTS5 support once per process."""
    global _FTS_AVAILABLE
    if _FTS_AVAILABLE is not None:
        return _FTS_AVAILABLE
    try:
        with get_db() as conn:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS __fts_test USING fts5(x)")
            conn.execute("DROP TABLE IF EXISTS __fts_test")
        _FTS_AVAILABLE = True
        log.info("FTS5 available")
    except Exception as e:
        _FTS_AVAILABLE = False
        log.warning("FTS5 unavailable, falling back to LIKE: %s", e)
    return _FTS_AVAILABLE


def init_fts() -> None:
    """Create FTS5 tables + triggers (or LIKE indexes if unavailable)."""
    if not fts_available():
        return
    try:
        with get_db() as conn:
            conn.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS calc_fts USING fts5(
                    expression, result,
                    content='calculations',
                    content_rowid='id',
                    tokenize='unicode61'
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS chat_fts USING fts5(
                    username, body,
                    content='chat_messages',
                    content_rowid='id',
                    tokenize='unicode61'
                );

                CREATE TRIGGER IF NOT EXISTS calc_fts_ai AFTER INSERT ON calculations BEGIN
                    INSERT INTO calc_fts(rowid, expression, result)
                    VALUES (new.id, new.expression, new.result);
                END;
                CREATE TRIGGER IF NOT EXISTS calc_fts_ad AFTER DELETE ON calculations BEGIN
                    INSERT INTO calc_fts(calc_fts, rowid, expression, result)
                    VALUES ('delete', old.id, old.expression, old.result);
                END;
                CREATE TRIGGER IF NOT EXISTS calc_fts_au AFTER UPDATE ON calculations BEGIN
                    INSERT INTO calc_fts(calc_fts, rowid, expression, result)
                    VALUES ('delete', old.id, old.expression, old.result);
                    INSERT INTO calc_fts(rowid, expression, result)
                    VALUES (new.id, new.expression, new.result);
                END;

                CREATE TRIGGER IF NOT EXISTS chat_fts_ai AFTER INSERT ON chat_messages BEGIN
                    INSERT INTO chat_fts(rowid, username, body)
                    VALUES (new.id, new.username, new.body);
                END;
                CREATE TRIGGER IF NOT EXISTS chat_fts_ad AFTER DELETE ON chat_messages BEGIN
                    INSERT INTO chat_fts(chat_fts, rowid, username, body)
                    VALUES ('delete', old.id, old.username, old.body);
                END;
                CREATE TRIGGER IF NOT EXISTS chat_fts_au AFTER UPDATE ON chat_messages BEGIN
                    INSERT INTO chat_fts(chat_fts, rowid, username, body)
                    VALUES ('delete', old.id, old.username, old.body);
                    INSERT INTO chat_fts(rowid, username, body)
                    VALUES (new.id, new.username, new.body);
                END;
            """)
            # Backfill once
            conn.execute("""
                INSERT INTO calc_fts(rowid, expression, result)
                SELECT id, expression, result FROM calculations
                WHERE id NOT IN (SELECT rowid FROM calc_fts)
            """)
            conn.execute("""
                INSERT INTO chat_fts(rowid, username, body)
                SELECT id, username, body FROM chat_messages
                WHERE id NOT IN (SELECT rowid FROM chat_fts)
            """)
        log.info("FTS5 tables initialized")
    except Exception as e:
        log.error("FTS5 init failed: %s", e, exc_info=True)


def _escape_fts(q: str) -> str:
    """Escape user input for FTS5 MATCH (avoid syntax errors)."""
    # Wrap tokens in double quotes; escape embedded quotes
    tokens = [t.strip() for t in q.split() if t.strip()]
    return " ".join(f'"{t.replace(chr(34), chr(34)*2)}"' for t in tokens)


@search_bp.route("", methods=["GET"])
@require_auth
@rate_limit(max_calls=60, window_seconds=60)
def search():
    q = (request.args.get("q") or "").strip()
    scope = (request.args.get("scope") or "all").lower()
    room_filter = (request.args.get("room") or "").strip()
    if not q:
        return jsonify({"query": q, "results": [], "count": 0, "engine": "none"})
    if len(q) > 200:
        return jsonify({"error": "query too long (max 200)"}), 400

    try:
        limit = min(int(request.args.get("limit", 20)), 100)
    except ValueError:
        limit = 20

    results = []
    engine = "fts5" if fts_available() else "like"

    with get_db() as conn:
        if scope in ("all", "calculations"):
            if fts_available():
                try:
                    rows = conn.execute(
                        "SELECT c.id, c.expression, c.result, c.created_at, "
                        "  bm25(calc_fts) AS score "
                        "FROM calc_fts JOIN calculations c ON c.id = calc_fts.rowid "
                        "WHERE calc_fts MATCH ? AND c.user_id = ? "
                        "ORDER BY score LIMIT ?",
                        (_escape_fts(q), g.user_id, limit),
                    ).fetchall()
                except Exception as e:
                    log.warning("FTS calc query failed: %s", e)
                    rows = []
            else:
                like = f"%{q}%"
                rows = conn.execute(
                    "SELECT id, expression, result, created_at, 0 AS score "
                    "FROM calculations WHERE user_id = ? "
                    "  AND (expression LIKE ? OR result LIKE ?) "
                    "ORDER BY created_at DESC LIMIT ?",
                    (g.user_id, like, like, limit),
                ).fetchall()
            for r in rows:
                d = dict(r)
                d["kind"] = "calculation"
                results.append(d)

        if scope in ("all", "chat"):
            if fts_available():
                try:
                    if room_filter:
                        rows = conn.execute(
                            "SELECT m.id, m.username, m.body, m.room_id, m.created_at, "
                            "  bm25(chat_fts) AS score "
                            "FROM chat_fts JOIN chat_messages m ON m.id = chat_fts.rowid "
                            "WHERE chat_fts MATCH ? AND m.room_id = ? "
                            "ORDER BY score LIMIT ?",
                            (_escape_fts(q), room_filter, limit),
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            "SELECT m.id, m.username, m.body, m.room_id, m.created_at, "
                            "  bm25(chat_fts) AS score "
                            "FROM chat_fts JOIN chat_messages m ON m.id = chat_fts.rowid "
                            "WHERE chat_fts MATCH ? ORDER BY score LIMIT ?",
                            (_escape_fts(q), limit),
                        ).fetchall()
                except Exception as e:
                    log.warning("FTS chat query failed: %s", e)
                    rows = []
                except Exception as e:
                    log.warning("FTS chat query failed: %s", e)
                    rows = []
            else:
                like = f"%{q}%"
                if room_filter:
                    rows = conn.execute(
                        "SELECT id, username, body, room_id, created_at, 0 AS score "
                        "FROM chat_messages WHERE room_id = ? "
                        "  AND (body LIKE ? OR username LIKE ?) "
                        "ORDER BY created_at DESC LIMIT ?",
                        (room_filter, like, like, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, username, body, room_id, created_at, 0 AS score "
                        "FROM chat_messages WHERE body LIKE ? OR username LIKE ? "
                        "ORDER BY created_at DESC LIMIT ?",
                        (like, like, limit),
                    ).fetchall()
            for r in rows:
                d = dict(r)
                d["kind"] = "chat"
                results.append(d)

    return jsonify({
        "query": q,
        "scope": scope,
        "room": room_filter or None,
        "engine": engine,
        "results": results,
        "count": len(results),
    })
