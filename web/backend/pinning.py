"""Message pinning (Phase 51).

Endpoints:
    GET    /api/rooms/<room>/pins             list pinned
    POST   /api/rooms/<room>/pins             {message_id, note?}
    DELETE /api/rooms/<room>/pins/<message_id>  unpin
"""
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

pins_bp = Blueprint("pins", __name__, url_prefix="/api/rooms")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MAX_NOTE = 200
MAX_PINS = 50


def _validate_room(room):
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


@pins_bp.route("/<room>/pins", methods=["GET"])
@require_auth
def list_pins(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        rows = conn.execute("""
            SELECT p.id, p.message_id, p.note, p.created_at,
                   u.username AS pinned_by,
                   m.username AS author,
                   m.body, m.encrypted, m.kind, m.attachment_id
            FROM pinned_messages p
            JOIN users u ON u.id = p.pinned_by
            LEFT JOIN chat_messages m ON m.id = p.message_id
            WHERE p.room_id = ?
            ORDER BY p.created_at DESC
            LIMIT ?
        """, (room, MAX_PINS)).fetchall()
    return jsonify({"room": room, "pins": [dict(r) for r in rows], "count": len(rows)})


@pins_bp.route("/<room>/pins", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def add_pin(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    message_id = data.get("message_id")
    note = (data.get("note") or "").strip()[:MAX_NOTE] or None
    if not isinstance(message_id, int):
        return jsonify({"error": "message_id must be an integer"}), 400

    with get_db() as conn:
        # Verify the message exists in this room
        msg = conn.execute(
            "SELECT id FROM chat_messages WHERE id = ? AND room_id = ?",
            (message_id, room),
        ).fetchone()
        if not msg:
            return jsonify({"error": "Message not found in this room"}), 404

        # Enforce limit
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM pinned_messages WHERE room_id = ?", (room,),
        ).fetchone()["n"]
        if count >= MAX_PINS:
            return jsonify({"error": f"Pin limit reached ({MAX_PINS})"}), 409

        try:
            conn.execute(
                "INSERT INTO pinned_messages (room_id, message_id, pinned_by, note) "
                "VALUES (?, ?, ?, ?)",
                (room, message_id, g.user_id, note),
            )
        except Exception:
            return jsonify({"error": "Already pinned"}), 409

    log_event("room.pin", actor_id=g.user_id, resource="room",
              resource_id=room, details={"message_id": message_id})
    return jsonify({"room": room, "message_id": message_id, "note": note}), 201


@pins_bp.route("/<room>/pins/<int:message_id>", methods=["DELETE"])
@require_auth
def remove_pin(room, message_id):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM pinned_messages WHERE room_id = ? AND message_id = ?",
            (room, message_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not pinned"}), 404
    log_event("room.unpin", actor_id=g.user_id, resource="room",
              resource_id=room, details={"message_id": message_id})
    return jsonify({"unpinned": message_id})
