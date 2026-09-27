"""Wiki full-text search (Phase 80).

Uses SQLite FTS5 (falls back to LIKE when FTS5 is unavailable).

Endpoints:
    GET /api/wiki/search?q=...&room=...&limit=20
"""
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

ws_bp = Blueprint("wiki_search", __name__, url_prefix="/api/wiki")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_FTS_AVAILABLE = None


def fts_available() -> bool:
    global _FTS_AVAILABLE
    if _FTS_AVAILABLE is not None:
        return _FTS_AVAILABLE
    try:
        with get_db() as conn:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS __ws_test USING fts5(x)")
            conn.execute("DROP TABLE IF EXISTS __ws_test")
        _FTS_AVAILABLE = True
    except Exception:
        _FTS_AVAILABLE = False
    return _FTS_AVAILABLE


def _escape_fts(q: str) -> str:
    tokens = [t.strip() for t in q.split() if t.strip()]
    return " ".join(f'"{t.replace(chr(34), chr(34)*2)}"' for t in tokens)


def _snippet(body: str, q: str, width: int = 120) -> str:
    """Return a snippet of body centered on the first match of q."""
    if not body:
        return ""
    lower = body.lower()
    ql = q.lower()
    idx = lower.find(ql)
    if idx < 0:
        return body[:width] + ("…" if len(body) > width else "")
    start = max(0, idx - width // 3)
    end = min(len(body), idx + width)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(body) else ""
    return prefix + body[start:end] + suffix


@ws_bp.route("/search", methods=["GET"])
@require_auth
@rate_limit(max_calls=60, window_seconds=60)
def search():
    q = (request.args.get("q") or "").strip()
    room = (request.args.get("room") or "").strip()
    if not q:
        return jsonify({"query": q, "results": [], "count": 0, "engine": "none"})
    if len(q) > 200:
        return jsonify({"error": "query too long (max 200)"}), 400
    if room and not ROOM_RE.match(room):
        return jsonify({"error": "Invalid room name"}), 400

    try:
        limit = min(int(request.args.get("limit", 20)), 100)
    except ValueError:
        limit = 20

    results = []
    engine = "fts5" if fts_available() else "like"

    with get_db() as conn:
        if fts_available():
            try:
                if room:
                    rows = conn.execute("""
                        SELECT p.id, p.room_id, p.title, p.slug, p.body,
                               bm25(wiki_fts) AS score
                        FROM wiki_fts
                        JOIN wiki_pages p ON p.rowid = wiki_fts.rowid
                        WHERE wiki_fts MATCH ? AND p.room_id = ?
                        ORDER BY score LIMIT ?
                    """, (_escape_fts(q), room, limit)).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT p.id, p.room_id, p.title, p.slug, p.body,
                               bm25(wiki_fts) AS score
                        FROM wiki_fts
                        JOIN wiki_pages p ON p.rowid = wiki_fts.rowid
                        WHERE wiki_fts MATCH ?
                        ORDER BY score LIMIT ?
                    """, (_escape_fts(q), limit)).fetchall()
            except Exception:
                rows = []
        else:
            like = f"%{q}%"
            if room:
                rows = conn.execute("""
                    SELECT id, room_id, title, slug, body, 0 AS score
                    FROM wiki_pages
                    WHERE room_id = ? AND (title LIKE ? OR body LIKE ?)
                    ORDER BY updated_at DESC LIMIT ?
                """, (room, like, like, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT id, room_id, title, slug, body, 0 AS score
                    FROM wiki_pages
                    WHERE title LIKE ? OR body LIKE ?
                    ORDER BY updated_at DESC LIMIT ?
                """, (like, like, limit)).fetchall()

    for r in rows:
        results.append({
            "id": r["id"],
            "room_id": r["room_id"],
            "title": r["title"],
            "slug": r["slug"],
            "snippet": _snippet(r["body"] or "", q),
            "score": r["score"],
        })

    return jsonify({
        "query": q,
        "room": room or None,
        "engine": engine,
        "results": results,
        "count": len(results),
    })
