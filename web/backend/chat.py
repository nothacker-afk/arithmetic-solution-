"""Chat REST blueprint.

Endpoints:
    GET  /api/chat/<room>              - list recent messages
    POST /api/chat/<room>              - post a message
    DELETE /api/chat/<room>            - clear room history

Messages may be plaintext or client-encrypted. When encrypted=1 the
server treats `body` as opaque base64 ciphertext and never inspects it.
"""
from flask import Blueprint, request, jsonify

from .database import get_db
from .rate_limit import rate_limit

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

MAX_BODY_BYTES = 4096
MAX_ROOM_LEN = 64
MAX_USER_LEN = 32


def _validate_room(room: str) -> str:
    room = (room or "").strip()
    if not room or len(room) > MAX_ROOM_LEN:
        raise ValueError("Invalid room name")
    if not all(c.isalnum() or c in "-_" for c in room):
        raise ValueError("Room name must be alphanumeric (hyphens and underscores allowed)")
    return room


def _validate_user(u: str) -> str:
    u = (u or "").strip()[:MAX_USER_LEN]
    if not u:
        raise ValueError("Username required")
    return u


@chat_bp.route("/<room>", methods=["GET"])
def list_messages(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except ValueError:
        limit = 50

    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, body, encrypted, created_at "
            "FROM chat_messages WHERE room_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (room, limit),
        ).fetchall()

    # Reverse so oldest first
    messages = [dict(r) for r in reversed(rows)]
    return jsonify({"room": room, "messages": messages})


@chat_bp.route("/<room>", methods=["POST"])
@rate_limit(max_calls=60, window_seconds=60)
def post_message(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    try:
        username = _validate_user(data.get("username", ""))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    body = data.get("body") or ""
    if not isinstance(body, str) or not body.strip():
        return jsonify({"error": "Message body required"}), 400
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        return jsonify({"error": "Message too long"}), 400

    encrypted = 1 if data.get("encrypted") else 0

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO chat_messages (room_id, username, body, encrypted) "
            "VALUES (?, ?, ?, ?)",
            (room, username, body, encrypted),
        )
        msg_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, username, body, encrypted, created_at "
            "FROM chat_messages WHERE id = ?",
            (msg_id,),
        ).fetchone()

    return jsonify(dict(row)), 201


@chat_bp.route("/<room>", methods=["DELETE"])
def clear_messages(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        cur = conn.execute("DELETE FROM chat_messages WHERE room_id = ?", (room,))
        n = cur.rowcount
    return jsonify({"deleted_count": n})
