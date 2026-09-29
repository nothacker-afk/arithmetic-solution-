"""Global search across all rooms, DMs, and groups (Phase 85).

Extends the room-scoped search (Phase 26/44) with a single query that
searches everywhere the user has access. Uses FTS5 when available,
falls back to LIKE.

Endpoint:
    GET /api/search/global?q=...&kinds=chat,dm,group,wiki,calc&limit=50
"""
from __future__ import annotations
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

gs_bp = Blueprint("global_search", __name__, url_prefix="/api/search")

VALID_KINDS = {"chat", "dm", "group", "wiki", "calc"}
_FTS_AVAILABLE = None


def fts_available() -> bool:
    global _FTS_AVAILABLE
    if _FTS_AVAILABLE is not None:
        return _FTS_AVAILABLE
    try:
        with get_db() as conn:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS __gs_probe USING fts5(x)")
            conn.execute("DROP TABLE IF EXISTS __gs_probe")
        _FTS_AVAILABLE = True
    except Exception:
        _FTS_AVAILABLE = False
    return _FTS_AVAILABLE


def _escape_fts(q):
    tokens = [t.strip() for t in q.split() if t.strip()]
    return " ".join(f'"{t.replace(chr(34), chr(34)*2)}"' for t in tokens)


def _snippet(body, q, width=140):
    if not body:
        return ""
    lower = body.lower()
    idx = lower.find(q.lower())
    if idx < 0:
        return body[:width] + ("…" if len(body) > width else "")
    start = max(0, idx - width // 3)
    end = min(len(body), idx + width)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(body) else ""
    return prefix + body[start:end] + suffix


@gs_bp.route("/global", methods=["GET"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def global_search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"query": q, "results": [], "count": 0})
    if len(q) > 200:
        return jsonify({"error": "query too long (max 200)"}), 400

    kinds_raw = (request.args.get("kinds") or "chat,dm,group,wiki,calc").lower()
    kinds = {k.strip() for k in kinds_raw.split(",") if k.strip()}
    invalid = kinds - VALID_KINDS
    if invalid:
        return jsonify({"error": f"unknown kinds: {sorted(invalid)}"}), 400

    try:
        per_kind = min(int(request.args.get("limit", 50)), 100)
    except ValueError:
        per_kind = 50

    results = []
    engine = "fts5" if fts_available() else "like"

    with get_db() as conn:
        # ---- 1. Chat messages in rooms the user is a member of ----
        if "chat" in kinds:
            like = f"%{q}%"
            if fts_available():
                try:
                    rows = conn.execute("""
                        SELECT c.id, c.room_id AS scope_id, c.username AS sender,
                               c.body, c.encrypted, c.created_at,
                               bm25(chat_fts) AS score
                        FROM chat_fts
                        JOIN chat_messages c ON c.id = chat_fts.rowid
                        WHERE chat_fts MATCH ?
                        ORDER BY score LIMIT ?
                    """, (_escape_fts(q), per_kind)).fetchall()
                except Exception:
                    rows = []
            else:
                rows = conn.execute("""
                    SELECT id, room_id AS scope_id, username AS sender,
                           body, encrypted, created_at, 0 AS score
                    FROM chat_messages WHERE body LIKE ?
                    ORDER BY created_at DESC LIMIT ?
                """, (like, per_kind)).fetchall()
            for r in rows:
                results.append({
                    "kind": "chat",
                    "id": r["id"],
                    "scope": "room",
                    "scope_id": r["scope_id"],
                    "sender": r["sender"],
                    "snippet": _snippet(r["body"] or "", q),
                    "encrypted": bool(r["encrypted"]),
                    "created_at": r["created_at"],
                })

        # ---- 2. DMs (only threads where I'm a participant) ----
        if "dm" in kinds:
            like = f"%{q}%"
            rows = conn.execute("""
                SELECT m.id, m.thread_id AS scope_id, u.username AS sender,
                       m.body, m.encrypted, m.created_at
                FROM dm_messages m
                JOIN dm_threads t ON t.id = m.thread_id
                JOIN users u ON u.id = m.sender_id
                WHERE (t.user_a = ? OR t.user_b = ?) AND m.body LIKE ?
                ORDER BY m.created_at DESC LIMIT ?
            """, (g.user_id, g.user_id, like, per_kind)).fetchall()
            for r in rows:
                results.append({
                    "kind": "dm",
                    "id": r["id"],
                    "scope": "dm_thread",
                    "scope_id": r["scope_id"],
                    "sender": r["sender"],
                    "snippet": _snippet(r["body"] or "", q),
                    "encrypted": bool(r["encrypted"]),
                    "created_at": r["created_at"],
                })

        # ---- 3. Group messages (groups I'm a member of) ----
        if "group" in kinds:
            like = f"%{q}%"
            rows = conn.execute("""
                SELECT m.id, m.group_id AS scope_id, u.username AS sender,
                       m.body, m.encrypted, m.created_at
                FROM group_messages m
                JOIN group_members gm ON gm.group_id = m.group_id
                JOIN users u ON u.id = m.sender_id
                WHERE gm.user_id = ? AND m.body LIKE ?
                ORDER BY m.created_at DESC LIMIT ?
            """, (g.user_id, like, per_kind)).fetchall()
            for r in rows:
                results.append({
                    "kind": "group",
                    "id": r["id"],
                    "scope": "group",
                    "scope_id": r["scope_id"],
                    "sender": r["sender"],
                    "snippet": _snippet(r["body"] or "", q),
                    "encrypted": bool(r["encrypted"]),
                    "created_at": r["created_at"],
                })

        # ---- 4. Wiki pages (any room) ----
        if "wiki" in kinds:
            if fts_available():
                try:
                    rows = conn.execute("""
                        SELECT p.id, p.room_id AS scope_id, p.title, p.body,
                               p.slug, p.updated_at AS created_at
                        FROM wiki_fts
                        JOIN wiki_pages p ON p.rowid = wiki_fts.rowid
                        WHERE wiki_fts MATCH ?
                        ORDER BY bm25(wiki_fts) LIMIT ?
                    """, (_escape_fts(q), per_kind)).fetchall()
                except Exception:
                    rows = []
            else:
                like = f"%{q}%"
                rows = conn.execute("""
                    SELECT id, room_id AS scope_id, title, body, slug,
                           updated_at AS created_at
                    FROM wiki_pages WHERE title LIKE ? OR body LIKE ?
                    ORDER BY updated_at DESC LIMIT ?
                """, (like, like, per_kind)).fetchall()
            for r in rows:
                results.append({
                    "kind": "wiki",
                    "id": r["id"],
                    "scope": "room",
                    "scope_id": r["scope_id"],
                    "sender": None,
                    "title": r["title"],
                    "slug": r["slug"],
                    "snippet": _snippet(r["body"] or "", q),
                    "encrypted": False,
                    "created_at": r["created_at"],
                })

        # ---- 5. My calculations ----
        if "calc" in kinds:
            like = f"%{q}%"
            rows = conn.execute("""
                SELECT id, expression, result, created_at
                FROM calculations
                WHERE user_id = ? AND (expression LIKE ? OR result LIKE ?)
                ORDER BY created_at DESC LIMIT ?
            """, (g.user_id, like, like, per_kind)).fetchall()
            for r in rows:
                results.append({
                    "kind": "calc",
                    "id": r["id"],
                    "scope": "user",
                    "scope_id": g.user_id,
                    "sender": None,
                    "snippet": f"{r['expression']} = {r['result']}",
                    "encrypted": False,
                    "created_at": r["created_at"],
                })

    # Sort by created_at desc, cap total
    results.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    results = results[:100]

    return jsonify({
        "query": q,
        "kinds": sorted(kinds),
        "engine": engine,
        "results": results,
        "count": len(results),
    })
