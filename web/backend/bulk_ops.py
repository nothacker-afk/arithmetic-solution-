"""Bulk message operations (Phase 74).

Endpoints:
    POST /api/rooms/<room>/messages/bulk
        {
          action: "delete" | "restore" | "move",
          message_ids: [1, 2, 3],
          target_room: "other-room"   (only for move)
        }
    GET /api/rooms/<room>/bulk_operations     audit trail

Authorization:
    - Deleting your own messages: always allowed.
    - Deleting others' messages: requires can_delete_others permission
      (Phase 76 RBAC), or ownership of the room.
    - Move: only within rooms where you have can_manage_wiki or owner.
"""
import re
import json

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

bulk_bp = Blueprint("bulk_ops", __name__, url_prefix="/api/rooms")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MAX_IDS = 200
VALID_ACTIONS = {"delete", "restore", "move"}


def _validate_room(room):
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


def _is_owner(conn, room, user_id):
    row = conn.execute("SELECT owner_id FROM rooms WHERE name = ?", (room,)).fetchone()
    return row and row["owner_id"] == user_id


def _can_delete_others(conn, room, user_id):
    if _is_owner(conn, room, user_id):
        return True
    try:
        from .rbac import has_permission
        return has_permission(conn, room, user_id, "can_delete_others")
    except Exception:
        return False


@bulk_bp.route("/<room>/messages/bulk", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def bulk_action(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").lower()
    ids = data.get("message_ids") or []
    target_room = (data.get("target_room") or "").strip() or None

    if action not in VALID_ACTIONS:
        return jsonify({"error": f"action must be one of {sorted(VALID_ACTIONS)}"}), 400
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "message_ids must be a non-empty list"}), 400
    if len(ids) > MAX_IDS:
        return jsonify({"error": f"max {MAX_IDS} ids per request"}), 400
    try:
        ids = [int(x) for x in ids]
    except (TypeError, ValueError):
        return jsonify({"error": "message_ids must be integers"}), 400

    if action == "move":
        if not target_room:
            return jsonify({"error": "target_room required for move"}), 400
        if not ROOM_RE.match(target_room):
            return jsonify({"error": "Invalid target_room"}), 400

    placeholders = ",".join("?" for _ in ids)
    affected = 0

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT id, username FROM chat_messages
            WHERE room_id = ? AND id IN ({placeholders})
        """, (room, *ids)).fetchall()

        # Authorization check: how many are mine vs others
        me = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
        me_name = me["username"] if me else ""

        others = [r for r in rows if r["username"] != me_name]
        if others and not _can_delete_others(conn, room, g.user_id):
            return jsonify({
                "error": "You don't have permission to modify others' messages",
                "others_count": len(others),
            }), 403

        if action == "delete":
            cur = conn.execute(f"""
                UPDATE chat_messages SET deleted = 1, body = '',
                    attachment_id = NULL, edited_at = CURRENT_TIMESTAMP
                WHERE room_id = ? AND id IN ({placeholders})
            """, (room, *ids))
            affected = cur.rowcount

        elif action == "restore":
            # Only the author can restore their own
            cur = conn.execute(f"""
                UPDATE chat_messages SET deleted = 0, edited_at = CURRENT_TIMESTAMP
                WHERE room_id = ? AND username = ? AND id IN ({placeholders})
            """, (room, me_name, *ids))
            affected = cur.rowcount

        elif action == "move":
            if not _is_owner(conn, room, g.user_id):
                return jsonify({"error": "Only the source room owner can move messages"}), 403
            if not _is_owner(conn, target_room, g.user_id) and not _is_owner(conn, target_room, g.user_id):
                # Allow if I'm the target owner too
                row = conn.execute("SELECT owner_id FROM rooms WHERE name = ?",
                                   (target_room,)).fetchone()
                if not row or row["owner_id"] != g.user_id:
                    return jsonify({"error": "Only the target room owner can receive moves"}), 403
            cur = conn.execute(f"""
                UPDATE chat_messages SET room_id = ?
                WHERE room_id = ? AND id IN ({placeholders})
            """, (target_room, room, *ids))
            affected = cur.rowcount

        conn.execute("""
            INSERT INTO bulk_operations (room_id, action, actor_id, target_count, details)
            VALUES (?, ?, ?, ?, ?)
        """, (room, action, g.user_id, affected,
              json.dumps({"ids": ids, "target_room": target_room})))

    log_event(f"bulk.{action}", actor_id=g.user_id, resource="room",
              resource_id=room, details={"count": affected, "target": target_room})

    return jsonify({
        "room": room,
        "action": action,
        "affected": affected,
        "target_room": target_room,
    })


@bulk_bp.route("/<room>/bulk_operations", methods=["GET"])
@require_auth
def list_bulk_ops(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        if not _can_delete_others(conn, room, g.user_id):
            return jsonify({"error": "Permission denied"}), 403
        rows = conn.execute("""
            SELECT b.id, b.action, b.target_count, b.details, b.created_at,
                   u.username AS actor
            FROM bulk_operations b
            LEFT JOIN users u ON u.id = b.actor_id
            WHERE b.room_id = ?
            ORDER BY b.created_at DESC LIMIT 100
        """, (room,)).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        if d.get("details"):
            try:
                d["details"] = json.loads(d["details"])
            except Exception:
                pass
        out.append(d)
    return jsonify({"operations": out})
