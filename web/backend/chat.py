"""Chat REST blueprint.

Endpoints:
    GET    /api/chat/<room>                    list messages (with reply_count)
    POST   /api/chat/<room>                    post message (voice-aware)
    DELETE /api/chat/<room>                    clear room
    PATCH  /api/chat/<room>/<msg_id>           edit message
    DELETE /api/chat/<room>/<msg_id>           soft-delete (tombstone)
    GET    /api/chat/<room>/<msg_id>/edits     edit history
    GET    /api/chat/<room>/<parent_id>/replies  list replies
    GET    /api/chat/<room>/ttl                get disappearing TTL
    PUT    /api/chat/<room>/ttl                set disappearing TTL
"""
import re

from flask import Blueprint, request, jsonify

from .database import get_db
from .rate_limit import rate_limit

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

MAX_BODY_BYTES = 4096
ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _validate_room(room):
    room = (room or "").strip()
    if not ROOM_RE.match(room):
        raise ValueError("Invalid room name")
    return room


def _room_ttl_seconds(conn, room):
    row = conn.execute(
        "SELECT ttl_seconds FROM room_ttls WHERE room_id = ?", (room,)
    ).fetchone()
    return int(row["ttl_seconds"]) if row else 0


def _row_to_dict(row):
    """Convert a sqlite3.Row to a dict with safe defaults for new columns."""
    d = dict(row)
    d.setdefault("parent_id", None)
    d.setdefault("kind", "text")
    d.setdefault("attachment_id", None)
    d.setdefault("edited_at", None)
    d.setdefault("deleted", 0)
    d.setdefault("expires_at", None)
    d.setdefault("reply_count", 0)
    return d


def _safe_select(sql_star, fallback_sql):
    """Try the new SELECT; fall back if the DB is missing columns."""
    return sql_star, fallback_sql


# ---------------------------------------------------------------------
# List messages
# ---------------------------------------------------------------------
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
        # Try the full SELECT first
        try:
            rows = conn.execute(
                "SELECT c.id, c.username, c.body, c.encrypted, c.parent_id, "
                "       c.kind, c.attachment_id, c.edited_at, c.deleted, "
                "       c.expires_at, c.created_at, "
                "       (SELECT COUNT(*) FROM chat_messages r WHERE r.parent_id = c.id) "
                "         AS reply_count "
                "FROM chat_messages c WHERE c.room_id = ? "
                "ORDER BY c.id DESC LIMIT ?",
                (room, limit),
            ).fetchall()
        except Exception:
            # Fallback for old schemas
            rows = conn.execute(
                "SELECT id, username, body, encrypted, created_at "
                "FROM chat_messages WHERE room_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (room, limit),
            ).fetchall()

    out = [_row_to_dict(r) for r in reversed(rows)]
    return jsonify({"room": room, "messages": out})


# ---------------------------------------------------------------------
# Post a message (voice-aware + parent validation)
# ---------------------------------------------------------------------
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
    encrypted = 1 if data.get("encrypted") else 0

    if not username:
        return jsonify({"error": "username is required"}), 400

    if not isinstance(body, str):
        return jsonify({"error": "body must be a string"}), 400
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        return jsonify({"error": "Message too long"}), 400

    # Empty body is allowed ONLY for non-text kinds (voice, file)
    if kind == "text" and not body.strip():
        return jsonify({"error": "body is required"}), 400

    # Validate parent BEFORE insert
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
        ttl = _room_ttl_seconds(conn, room)

        try:
            cur = conn.execute(
                "INSERT INTO chat_messages "
                "(room_id, username, body, encrypted, parent_id, kind, "
                " attachment_id, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, "
                "  CASE WHEN ? > 0 THEN datetime('now', '+' || ? || ' seconds') "
                "       ELSE NULL END)",
                (room, username, body, encrypted, parent_id, kind,
                 attachment_id, ttl, ttl),
            )
        except Exception:
            # Fallback for old schema (no extra columns)
            cur = conn.execute(
                "INSERT INTO chat_messages "
                "(room_id, username, body, encrypted) VALUES (?, ?, ?, ?)",
                (room, username, body, encrypted),
            )
        msg_id = cur.lastrowid

        try:
            row = conn.execute(
                "SELECT id, username, body, encrypted, parent_id, kind, "
                "       attachment_id, edited_at, deleted, expires_at, created_at "
                "FROM chat_messages WHERE id = ?", (msg_id,),
            ).fetchone()
        except Exception:
            row = conn.execute(
                "SELECT id, username, body, encrypted, created_at "
                "FROM chat_messages WHERE id = ?", (msg_id,),
            ).fetchone()

    out = _row_to_dict(row)
    out["reply_count"] = 0
    return jsonify(out), 201


# ---------------------------------------------------------------------
# Clear room
# ---------------------------------------------------------------------
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


# ---------------------------------------------------------------------
# Edit message
# ---------------------------------------------------------------------
@chat_bp.route("/<room>/<int:msg_id>", methods=["PATCH"])
def edit_message(room, msg_id):
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
            "SELECT username, body FROM chat_messages WHERE id = ? AND room_id = ?",
            (msg_id, room),
        ).fetchone()
        if not row:
            return jsonify({"error": "Message not found"}), 404
        if row["username"] != username:
            return jsonify({"error": "Only the original author can edit"}), 403

        conn.execute(
            "INSERT INTO message_edits (message_kind, message_id, old_body, edited_by) "
            "VALUES ('chat', ?, ?, ?)",
            (msg_id, row["body"], None),
        )

        conn.execute(
            "UPDATE chat_messages SET body = ?, edited_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (new_body, msg_id),
        )
        updated = conn.execute(
            "SELECT id, username, body, encrypted, parent_id, kind, attachment_id, "
            "       edited_at, deleted, expires_at, created_at "
            "FROM chat_messages WHERE id = ?", (msg_id,),
        ).fetchone()

    out = _row_to_dict(updated)
    out["reply_count"] = 0
    return jsonify(out)


# ---------------------------------------------------------------------
# Delete message (tombstone)
# ---------------------------------------------------------------------
@chat_bp.route("/<room>/<int:msg_id>", methods=["DELETE"])
def delete_message(room, msg_id):
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


# ---------------------------------------------------------------------
# Edit history
# ---------------------------------------------------------------------
@chat_bp.route("/<room>/<int:msg_id>/edits", methods=["GET"])
def get_edits(room, msg_id):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        ok = conn.execute(
            "SELECT 1 FROM chat_messages WHERE id = ? AND room_id = ?",
            (msg_id, room),
        ).fetchone()
        if not ok:
            return jsonify({"error": "Message not found"}), 404
        try:
            rows = conn.execute(
                "SELECT old_body, created_at FROM message_edits "
                "WHERE message_kind = 'chat' AND message_id = ? ORDER BY id DESC",
                (msg_id,),
            ).fetchall()
        except Exception:
            rows = []
    return jsonify({"edits": [dict(r) for r in rows]})


# ---------------------------------------------------------------------
# Thread replies
# ---------------------------------------------------------------------
@chat_bp.route("/<room>/<int:parent_id>/replies", methods=["GET"])
def list_replies(room, parent_id):
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
        try:
            rows = conn.execute(
                "SELECT id, username, body, encrypted, parent_id, kind, "
                "       attachment_id, edited_at, deleted, expires_at, created_at "
                "FROM chat_messages WHERE parent_id = ? ORDER BY id ASC LIMIT 200",
                (parent_id,),
            ).fetchall()
        except Exception:
            rows = []
    return jsonify({
        "parent_id": parent_id,
        "replies": [_row_to_dict(r) for r in rows],
    })


# ---------------------------------------------------------------------
# Room TTL (disappearing messages)
# ---------------------------------------------------------------------
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
