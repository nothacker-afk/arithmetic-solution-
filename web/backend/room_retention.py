"""Room-level retention overrides (Phase 84).

Owners can override the global retention TTLs on a per-room basis.

Endpoints:
    GET    /api/rooms/<room>/retention         get current overrides
    PUT    /api/rooms/<room>/retention         set overrides
    DELETE /api/rooms/<room>/retention         reset to globals
"""
from __future__ import annotations
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

retention_bp = Blueprint("room_retention", __name__, url_prefix="/api/rooms")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _validate_room(room):
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


def _is_owner(conn, room, user_id):
    row = conn.execute("SELECT owner_id FROM rooms WHERE name = ?", (room,)).fetchone()
    return row and row["owner_id"] == user_id


def _validate_days(value, field):
    """None = inherit global. int 0..3650 = explicit."""
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer")
    if n < 0 or n > 3650:
        raise ValueError(f"{field} must be 0..3650")
    return n


@retention_bp.route("/<room>/retention", methods=["GET"])
@require_auth
def get_retention(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        row = conn.execute("""
            SELECT message_days, chat_days, audit_days, updated_at, updated_by
            FROM room_retention_overrides WHERE room_id = ?
        """, (room,)).fetchone()

    if not row:
        return jsonify({
            "room": room,
            "message_days": None,
            "chat_days": None,
            "audit_days": None,
            "is_custom": False,
        })
    return jsonify({
        "room": room,
        "message_days": row["message_days"],
        "chat_days": row["chat_days"],
        "audit_days": row["audit_days"],
        "updated_at": row["updated_at"],
        "is_custom": True,
    })


@retention_bp.route("/<room>/retention", methods=["PUT"])
@require_auth
@rate_limit(max_calls=20, window_seconds=60)
def set_retention(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    try:
        message_days = _validate_days(data.get("message_days"), "message_days")
        chat_days = _validate_days(data.get("chat_days"), "chat_days")
        audit_days = _validate_days(data.get("audit_days"), "audit_days")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        room_row = conn.execute(
            "SELECT owner_id FROM rooms WHERE name = ?", (room,),
        ).fetchone()
        if not room_row:
            return jsonify({"error": "Room not found"}), 404
        if room_row["owner_id"] != g.user_id:
            return jsonify({"error": "Only the room owner can set retention"}), 403

        conn.execute("""
            INSERT INTO room_retention_overrides
            (room_id, message_days, chat_days, audit_days, updated_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                message_days = excluded.message_days,
                chat_days = excluded.chat_days,
                audit_days = excluded.audit_days,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = excluded.updated_by
        """, (room, message_days, chat_days, audit_days, g.user_id))

    log_event("room.retention.set", actor_id=g.user_id, resource="room",
              resource_id=room,
              details={"message_days": message_days, "chat_days": chat_days,
                       "audit_days": audit_days})

    return jsonify({
        "room": room,
        "message_days": message_days,
        "chat_days": chat_days,
        "audit_days": audit_days,
        "is_custom": True,
    })


@retention_bp.route("/<room>/retention", methods=["DELETE"])
@require_auth
def reset_retention(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        room_row = conn.execute(
            "SELECT owner_id FROM rooms WHERE name = ?", (room,),
        ).fetchone()
        if not room_row:
            return jsonify({"error": "Room not found"}), 404
        if room_row["owner_id"] != g.user_id:
            return jsonify({"error": "Only the room owner can reset retention"}), 403
        cur = conn.execute(
            "DELETE FROM room_retention_overrides WHERE room_id = ?", (room,),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "No custom retention to reset"}), 404

    log_event("room.retention.reset", actor_id=g.user_id,
              resource="room", resource_id=room)
    return jsonify({"room": room, "reset": True, "is_custom": False})


# ---------------------------------------------------------------------
# Helper for jobs.run_retention()
# ---------------------------------------------------------------------
def apply_room_overrides(conn) -> dict:
    """Delete per-room rows according to overrides. Returns {room: count}."""
    deleted = {}
    rows = conn.execute("""
        SELECT room_id, message_days, chat_days, audit_days
        FROM room_retention_overrides
    """).fetchall()

    for r in rows:
        rid = r["room_id"]
        n_total = 0

        # Chat messages in this room
        if r["chat_days"] is not None and r["chat_days"] > 0:
            cur = conn.execute(
                "DELETE FROM chat_messages WHERE room_id = ? "
                "  AND created_at < datetime('now', '-' || ? || ' days')",
                (rid, r["chat_days"]),
            )
            n_total += cur.rowcount

        # Calculations aren't room-scoped; message_days applies to chat only
        # (reserved for future per-room message retention)

        # Audit entries for this room
        if r["audit_days"] is not None and r["audit_days"] > 0:
            cur = conn.execute(
                "DELETE FROM audit_log WHERE resource_id = ? AND resource = 'room' "
                "  AND created_at < datetime('now', '-' || ? || ' days')",
                (rid, r["audit_days"]),
            )
            n_total += cur.rowcount

        if n_total:
            deleted[rid] = n_total

    return deleted
