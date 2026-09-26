"""Public room discovery (Phase 42).

Endpoints:
    GET    /api/discover/rooms            browse public rooms
    GET    /api/discover/rooms/<room>     single public room detail
    POST   /api/rooms/<room>/publish      {description, tags} — owner only
    DELETE /api/rooms/<room>/publish      unpublish
    PUT    /api/rooms/<room>/description  {description, tags} — owner only
"""
from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

discover_bp = Blueprint("discover", __name__, url_prefix="/api/discover")
rooms_extra_bp = Blueprint("rooms_extra", __name__, url_prefix="/api/rooms")


def _validate_room(name):
    import re
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", name or ""):
        raise ValueError("Invalid room name")
    return name


def _is_owner(conn, room, user_id):
    row = conn.execute("SELECT owner_id FROM rooms WHERE name = ?", (room,)).fetchone()
    return row and row["owner_id"] == user_id


# ---------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------
@discover_bp.route("/rooms", methods=["GET"])
def browse():
    q = (request.args.get("q") or "").strip().lower()
    tag = (request.args.get("tag") or "").strip().lower()
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except ValueError:
        limit = 50

    with get_db() as conn:
        rows = conn.execute("""
            SELECT r.name, r.created_at, r.owner_id,
                   u.username AS owner,
                   m.description, m.tags, m.published_at,
                   (SELECT COUNT(*) FROM room_members WHERE room_name = r.name) AS member_count,
                   (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.name) AS message_count
            FROM rooms r
            JOIN room_meta m ON m.room_id = r.name
            LEFT JOIN users u ON u.id = r.owner_id
            WHERE m.published = 1
            ORDER BY m.published_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        if q and q not in (d.get("name") or "").lower() and \
           q not in (d.get("description") or "").lower():
            continue
        if tag:
            tags = (d.get("tags") or "").lower()
            if tag not in [t.strip() for t in tags.split(",")]:
                continue
        out.append(d)

    return jsonify({"rooms": out, "count": len(out)})


@discover_bp.route("/rooms/<room>", methods=["GET"])
def room_detail(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        r = conn.execute("""
            SELECT r.name, r.created_at, u.username AS owner,
                   m.description, m.tags, m.published_at,
                   (SELECT COUNT(*) FROM room_members WHERE room_name = r.name) AS member_count
            FROM rooms r
            JOIN room_meta m ON m.room_id = r.name
            LEFT JOIN users u ON u.id = r.owner_id
            WHERE r.name = ? AND m.published = 1
        """, (room,)).fetchone()

    if not r:
        return jsonify({"error": "Room not published or not found"}), 404
    return jsonify(dict(r))


@discover_bp.route("/tags", methods=["GET"])
def all_tags():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT tags FROM room_meta WHERE published = 1 AND tags IS NOT NULL"
        ).fetchall()
    tag_set = set()
    for r in rows:
        for t in (r["tags"] or "").split(","):
            t = t.strip().lower()
            if t:
                tag_set.add(t)
    return jsonify({"tags": sorted(tag_set)})


# ---------------------------------------------------------------------
# Publish / unpublish / update description (owner only)
# ---------------------------------------------------------------------
@rooms_extra_bp.route("/<room>/publish", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def publish(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    description = (data.get("description") or "").strip()[:500]
    tags = (data.get("tags") or "").strip().lower()[:200]

    with get_db() as conn:
        if not _is_owner(conn, room, g.user_id):
            return jsonify({"error": "Only the owner can publish"}), 403
        conn.execute("""
            INSERT INTO room_meta (room_id, description, tags, published, published_at)
            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(room_id) DO UPDATE SET
                description = excluded.description,
                tags = excluded.tags,
                published = 1,
                published_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
        """, (room, description, tags))

    log_event("room.publish", actor_id=g.user_id, resource="room", resource_id=room)
    return jsonify({"room": room, "published": True,
                    "description": description, "tags": tags})


@rooms_extra_bp.route("/<room>/publish", methods=["DELETE"])
@require_auth
def unpublish(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        if not _is_owner(conn, room, g.user_id):
            return jsonify({"error": "Only the owner can unpublish"}), 403
        conn.execute("UPDATE room_meta SET published = 0 WHERE room_id = ?", (room,))
    log_event("room.unpublish", actor_id=g.user_id, resource="room", resource_id=room)
    return jsonify({"room": room, "published": False})


@rooms_extra_bp.route("/<room>/description", methods=["PUT"])
@require_auth
def update_description(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    description = (data.get("description") or "").strip()[:500]
    tags = (data.get("tags") or "").strip().lower()[:200]

    with get_db() as conn:
        if not _is_owner(conn, room, g.user_id):
            return jsonify({"error": "Only the owner can edit"}), 403
        conn.execute("""
            INSERT INTO room_meta (room_id, description, tags)
            VALUES (?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                description = excluded.description,
                tags = excluded.tags,
                updated_at = CURRENT_TIMESTAMP
        """, (room, description, tags))
    return jsonify({"room": room, "description": description, "tags": tags})


@rooms_extra_bp.route("/<room>/meta", methods=["GET"])
def get_meta(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        row = conn.execute(
            "SELECT description, tags, published, published_at "
            "FROM room_meta WHERE room_id = ?", (room,),
        ).fetchone()
    if not row:
        return jsonify({"room": room, "description": "", "tags": "", "published": False})
    return jsonify({"room": room, **dict(row)})
