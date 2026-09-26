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
    username = (data.get("username") or "").strip()[:32]
    body = data.get("body") or ""
    kind = (data.get("kind") or "text").strip()[:16]
    attachment_id = data.get("attachment_id")
    parent_id = data.get("parent_id")

    if not username:
        return jsonify({"error": "username is required"}), 400

    # Empty body allowed ONLY for non-text messages (voice/file)
    if kind == "text":
        if not isinstance(body, str) or not body.strip():
            return jsonify({"error": "body is required"}), 400

    if not isinstance(body, str):
        return jsonify({"error": "body must be a string"}), 400
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        return jsonify({"error": "Message too long"}), 400

    encrypted = 1 if data.get("encrypted") else 0

    # Validate parent before INSERT
    if parent_id is not None:
        if not isinstance(parent_id, int):
            return jsonify({"error": "parent_id must be an integer"}), 400
        with get_db() as conn:
            ok = conn.execute(
                "SELECT 1 FROM chat_messages WHERE id = ? AND room_id = ?",
                (parent_id, room),
            ).fetchone()
        if not ok:
            return jsonify({"error": "parent message not found in this room"}), 404

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO chat_messages "
            "(room_id, username, body, encrypted, parent_id, kind, attachment_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (room, username, body, encrypted, parent_id, kind, attachment_id),
        )
        msg_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, username, body, encrypted, parent_id, kind, "
            "       attachment_id, edited_at, deleted, expires_at, created_at "
            "FROM chat_messages WHERE id = ?",
            (msg_id,),
        ).fetchone()

    out = dict(row)
    out["reply_count"] = 0
    return jsonify(out), 201


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


@chat_bp.route("/<room>/<int:parent_id>/replies", methods=["GET"])
def list_replies(room, parent_id):
    """List direct replies to a message (single level, no nesting)."""
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        parent = conn.execute(
            "SELECT id FROM chat_messages WHERE id = ? AND room_id = ?",
            (parent_id, room),
        ).fetchone()
        if not parent:
            return jsonify({"error": "Parent not found"}), 404
        rows = conn.execute(
            "SELECT id, username, body, encrypted, parent_id, kind, "
            "       attachment_id, created_at "
            "FROM chat_messages WHERE parent_id = ? ORDER BY id ASC LIMIT 200",
            (parent_id,),
        ).fetchall()
    return jsonify({"parent_id": parent_id, "replies": [dict(r) for r in rows]})


@chat_bp.route("/<room>/<int:msg_id>", methods=["PATCH"])
def edit_message(room, msg_id):
    """Edit a chat message. Only the original sender can edit (auth or guest match)."""
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    new_body = (data.get("body") or "").strip()
    if not new_body:
        return jsonify({"error": "body required"}), 400
    if len(new_body.encode("utf-8")) > MAX_BODY_BYTES:
        return jsonify({"error": "Message too long"}), 400

    username = (data.get("username") or "").strip()[:32]
    if not username:
        return jsonify({"error": "username required for edit"}), 400

    with get_db() as conn:
        row = conn.execute(
            "SELECT username, body, encrypted FROM chat_messages WHERE id = ? AND room_id = ?",
            (msg_id, room),
        ).fetchone()
        if not row:
            return jsonify({"error": "Message not found"}), 404
        if row["username"] != username:
            return jsonify({"error": "Only the original author can edit"}), 403

        # Record edit history
        conn.execute(
            "INSERT INTO message_edits (message_kind, message_id, old_body, edited_by) "
            "VALUES ('chat', ?, ?, ?)",
            (msg_id, row["body"], 0),
        )
        conn.execute(
            "UPDATE chat_messages SET body = ?, edited_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_body, msg_id),
        )
        updated = conn.execute(
            "SELECT id, username, body, encrypted, parent_id, kind, attachment_id, "
            "       edited_at, deleted, expires_at, created_at "
            "FROM chat_messages WHERE id = ?",
            (msg_id,),
        ).fetchone()

    return jsonify(dict(updated))


@chat_bp.route("/<room>/<int:msg_id>", methods=["DELETE"])
def delete_message(room, msg_id):
    """Soft-delete a chat message (tombstone). Author only."""
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    username = (request.args.get("username") or "").strip()[:32]
    if not username:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()[:32]
    if not username:
        return jsonify({"error": "username required"}), 400

    with get_db() as conn:
        row = conn.execute(
            "SELECT username FROM chat_messages WHERE id = ? AND room_id = ?",
            (msg_id, room),
        ).fetchone()
        if not row:
            return jsonify({"error": "Message not found"}), 404
        if row["username"] != username:
            return jsonify({"error": "Only the original author can delete"}), 403

        conn.execute(
            "UPDATE chat_messages SET deleted = 1, body = '', "
            "attachment_id = NULL, edited_at = CURRENT_TIMESTAMP WHERE id = ?",
            (msg_id,),
        )

    return jsonify({"deleted": msg_id, "tombstone": True})


@chat_bp.route("/<room>/<int:msg_id>/edits", methods=["GET"])
def get_edits(room, msg_id):
    """Return the edit history for a message."""
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        # Ensure the message belongs to this room
        ok = conn.execute(
            "SELECT 1 FROM chat_messages WHERE id = ? AND room_id = ?",
            (msg_id, room),
        ).fetchone()
        if not ok:
            return jsonify({"error": "Message not found"}), 404

        rows = conn.execute(
            "SELECT old_body, created_at FROM message_edits "
            "WHERE message_kind = 'chat' AND message_id = ? "
            "ORDER BY id DESC",
            (msg_id,),
        ).fetchall()

    return jsonify({"edits": [dict(r) for r in rows]})


# ---------------------------------------------------------------------
# Disappearing messages (Phase 39)
# ---------------------------------------------------------------------
def _room_ttl_seconds(conn, room):
    row = conn.execute(
        "SELECT ttl_seconds FROM room_ttls WHERE room_id = ?", (room,),
    ).fetchone()
    return int(row["ttl_seconds"]) if row else 0


@chat_bp.route("/<room>/ttl", methods=["GET"])
def get_room_ttl(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        ttl = _room_ttl_seconds(conn, room)
    return jsonify({"room": room, "ttl_seconds": ttl})


@chat_bp.route("/<room>/ttl", methods=["PUT"])
def set_room_ttl(room):
    """Set the disappearing-message TTL for a room (0 = disabled)."""
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    data = request.get_json(silent=True) or {}
    try:
        ttl = int(data.get("ttl_seconds", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "ttl_seconds must be an integer"}), 400
    if ttl < 0 or ttl > 30 * 24 * 3600:
        return jsonify({"error": "ttl_seconds must be 0..2592000"}), 400
    with get_db() as conn:
        if ttl == 0:
            conn.execute("DELETE FROM room_ttls WHERE room_id = ?", (room,))
        else:
            conn.execute(
                "INSERT INTO room_ttls (room_id, ttl_seconds) VALUES (?, ?) "
                "ON CONFLICT(room_id) DO UPDATE SET ttl_seconds = excluded.ttl_seconds, "
                "updated_at = CURRENT_TIMESTAMP",
                (room, ttl),
            )
    return jsonify({"room": room, "ttl_seconds": ttl})
