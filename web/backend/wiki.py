"""Room wiki (Phase 52).

Each room can have shared wiki pages. Slugs are unique per room.

Endpoints:
    GET    /api/rooms/<room>/wiki              list pages
    POST   /api/rooms/<room>/wiki              {title, body} → creates
    GET    /api/rooms/<room>/wiki/<slug>       read a page
    PUT    /api/rooms/<room>/wiki/<slug>       {title?, body?} edit
    DELETE /api/rooms/<room>/wiki/<slug>       delete
"""
import re
import uuid

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

wiki_bp = Blueprint("wiki", __name__, url_prefix="/api/rooms")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MAX_BODY = 50000
MAX_TITLE = 200
MAX_PAGES_PER_ROOM = 100


def _validate_room(room):
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


def _slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return s[:64] or uuid.uuid4().hex[:8]


@wiki_bp.route("/<room>/wiki", methods=["GET"])
@require_auth
def list_pages(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, title, slug, updated_at, created_at,
                   LENGTH(body) AS body_length
            FROM wiki_pages WHERE room_id = ?
            ORDER BY updated_at DESC LIMIT ?
        """, (room, MAX_PAGES_PER_ROOM)).fetchall()
    return jsonify({"room": room, "pages": [dict(r) for r in rows], "count": len(rows)})


@wiki_bp.route("/<room>/wiki", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def create_page(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()[:MAX_TITLE]
    body = (data.get("body") or "")
    if not title:
        return jsonify({"error": "title required"}), 400
    if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_BODY:
        return jsonify({"error": f"body too long (max {MAX_BODY} bytes)"}), 400

    slug = _slugify(title)
    page_id = uuid.uuid4().hex

    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM wiki_pages WHERE room_id = ?", (room,),
        ).fetchone()["n"]
        if count >= MAX_PAGES_PER_ROOM:
            return jsonify({"error": f"Page limit reached ({MAX_PAGES_PER_ROOM})"}), 409

        # Ensure unique slug
        base_slug = slug
        i = 1
        while conn.execute("SELECT 1 FROM wiki_pages WHERE room_id = ? AND slug = ?",
                           (room, slug)).fetchone():
            slug = f"{base_slug}-{i}"
            i += 1

        conn.execute("""
            INSERT INTO wiki_pages (id, room_id, title, slug, body, created_by, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (page_id, room, title, slug, body, g.user_id, g.user_id))

    log_event("wiki.create", actor_id=g.user_id, resource="wiki",
              resource_id=page_id, details={"room": room, "slug": slug})
    return jsonify({"id": page_id, "room": room, "title": title,
                    "slug": slug, "body": body}), 201


@wiki_bp.route("/<room>/wiki/<slug>", methods=["GET"])
@require_auth
def get_page(room, slug):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        row = conn.execute("""
            SELECT p.id, p.title, p.slug, p.body, p.created_at, p.updated_at,
                   u.username AS created_by
            FROM wiki_pages p LEFT JOIN users u ON u.id = p.created_by
            WHERE p.room_id = ? AND p.slug = ?
        """, (room, slug)).fetchone()
    if not row:
        return jsonify({"error": "Page not found"}), 404
    return jsonify(dict(row))


@wiki_bp.route("/<room>/wiki/<slug>", methods=["PUT"])
@require_auth
def update_page(room, slug):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM wiki_pages WHERE room_id = ? AND slug = ?",
            (room, slug),
        ).fetchone()
        if not row:
            return jsonify({"error": "Page not found"}), 404

        sets = []
        params = []
        if "title" in data:
            t = (data.get("title") or "").strip()[:MAX_TITLE]
            if not t:
                return jsonify({"error": "title cannot be empty"}), 400
            sets.append("title = ?"); params.append(t)
        if "body" in data:
            b = data.get("body") or ""
            if not isinstance(b, str) or len(b.encode("utf-8")) > MAX_BODY:
                return jsonify({"error": "body too long"}), 400
            sets.append("body = ?"); params.append(b)
        if not sets:
            return jsonify({"error": "nothing to update"}), 400
        sets.append("updated_by = ?"); params.append(g.user_id)
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([room, slug])
        conn.execute(
            f"UPDATE wiki_pages SET {', '.join(sets)} WHERE room_id = ? AND slug = ?",
            tuple(params),
        )
        updated = conn.execute("""
            SELECT id, title, slug, body, created_at, updated_at
            FROM wiki_pages WHERE room_id = ? AND slug = ?
        """, (room, slug)).fetchone()

    log_event("wiki.update", actor_id=g.user_id, resource="wiki",
              resource_id=slug, details={"room": room})
    return jsonify(dict(updated))


@wiki_bp.route("/<room>/wiki/<slug>", methods=["DELETE"])
@require_auth
def delete_page(room, slug):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM wiki_pages WHERE room_id = ? AND slug = ?", (room, slug),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Page not found"}), 404
    log_event("wiki.delete", actor_id=g.user_id, resource="wiki",
              resource_id=slug, details={"room": room})
    return jsonify({"deleted": slug})
