"""Room chat read receipts (Phase 47).

Endpoints:
    POST /api/chat/<room>/read     {last_message_id}
    GET  /api/chat/<room>/reads?since=<msg_id>
"""
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

reads_bp = Blueprint("reads", __name__, url_prefix="/api/chat")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _validate_room(room):
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


@reads_bp.route("/<room>/read", methods=["POST"])
@require_auth
@rate_limit(max_calls=120, window_seconds=60)
def mark_read(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    last_id = data.get("last_message_id")
    if not isinstance(last_id, int) or last_id < 0:
        return jsonify({"error": "last_message_id must be a positive integer"}), 400

    with get_db() as conn:
        existing = conn.execute(
            "SELECT last_read_message_id FROM room_read_state "
            "WHERE room_id = ? AND user_id = ?", (room, g.user_id),
        ).fetchone()
        if existing and existing["last_read_message_id"] >= last_id:
            return jsonify({"room": room, "last_read_message_id":
                            existing["last_read_message_id"], "no_change": True})
        conn.execute("""
            INSERT INTO room_read_state (room_id, user_id, last_read_message_id, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(room_id, user_id) DO UPDATE SET
                last_read_message_id = excluded.last_read_message_id,
                updated_at = CURRENT_TIMESTAMP
        """, (room, g.user_id, last_id))
        me = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()

    # Broadcast to the room
    try:
        from .realtime import socketio
        socketio.emit("room_read", {
            "room": room,
            "username": me["username"] if me else "guest",
            "last_read_message_id": last_id,
        }, to=room)
    except Exception:
        pass

    return jsonify({"room": room, "last_read_message_id": last_id})


@reads_bp.route("/<room>/reads", methods=["GET"])
@require_auth
def list_reads(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        since = int(request.args.get("since", 0))
    except ValueError:
        since = 0

    with get_db() as conn:
        rows = conn.execute("""
            SELECT u.username, r.last_read_message_id, r.updated_at
            FROM room_read_state r JOIN users u ON u.id = r.user_id
            WHERE r.room_id = ? AND r.last_read_message_id >= ?
            ORDER BY r.updated_at DESC
        """, (room, since)).fetchall()

    return jsonify({
        "room": room,
        "since": since,
        "reads": [dict(r) for r in rows],
    })
