"""Room management blueprint (Phase 11).

Rooms are opt-in. An unclaimed room name behaves exactly like the open
rooms of Phases 9-10. Claiming a room gives it an owner, member list,
password gate, and invite system.
"""
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

from .config import Config
from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

rooms_bp = Blueprint("rooms", __name__, url_prefix="/api/rooms")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _validate_room(name):
    if not ROOM_RE.match(name or ""):
        raise ValueError("Invalid room name")
    return name


def _now():
    return datetime.now(timezone.utc)


def _get_room(conn, name):
    return conn.execute("SELECT * FROM rooms WHERE name = ?", (name,)).fetchone()


def _is_member(conn, room_name, user_id):
    return conn.execute(
        "SELECT 1 FROM room_members WHERE room_name = ? AND user_id = ?",
        (room_name, user_id),
    ).fetchone() is not None


# ---------------------------------------------------------------------
# Claim a room
# ---------------------------------------------------------------------
@rooms_bp.route("/<room>/claim", methods=["POST"])
@require_auth
def claim(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    password = data.get("password")

    with get_db() as conn:
        if _get_room(conn, room):
            return jsonify({"error": "Room already claimed"}), 409

        pw_hash = generate_password_hash(password) if password else None
        conn.execute(
            "INSERT INTO rooms (name, owner_id, password_hash, is_public) "
            "VALUES (?, ?, ?, 0)",
            (room, g.user_id, pw_hash),
        )
        conn.execute(
            "INSERT INTO room_members (room_name, user_id, role) "
            "VALUES (?, ?, 'owner')",
            (room, g.user_id),
        )

    return jsonify({
        "room": room,
        "owner_id": g.user_id,
        "has_password": password is not None,
    }), 201


# ---------------------------------------------------------------------
# Room info (public)
# ---------------------------------------------------------------------
@rooms_bp.route("/<room>", methods=["GET"])
def info(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        row = _get_room(conn, room)
        if not row:
            return jsonify({"room": room, "registered": False, "open": True})
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM room_members WHERE room_name = ?", (room,)
        ).fetchone()["n"]

    return jsonify({
        "room": room,
        "registered": True,
        "has_password": row["password_hash"] is not None,
        "is_public": bool(row["is_public"]),
        "member_count": n,
    })


# ---------------------------------------------------------------------
# Create invite (owner only)
# ---------------------------------------------------------------------
@rooms_bp.route("/<room>/invites", methods=["POST"])
@require_auth
@rate_limit(max_calls=20, window_seconds=60)
def create_invite(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        row = _get_room(conn, room)
        if not row:
            return jsonify({"error": "Room not registered"}), 404
        if row["owner_id"] != g.user_id:
            return jsonify({"error": "Only the owner can create invites"}), 403

        data = request.get_json(silent=True) or {}
        try:
            ttl_hours = int(data.get("ttl_hours", Config.INVITE_TTL_HOURS))
        except (TypeError, ValueError):
            ttl_hours = Config.INVITE_TTL_HOURS
        if ttl_hours < 1 or ttl_hours > Config.MAX_INVITE_TTL_HOURS:
            return jsonify({
                "error": f"ttl_hours must be 1-{Config.MAX_INVITE_TTL_HOURS}"
            }), 400

        import secrets
        token = secrets.token_urlsafe(32)
        expires_at = _now() + timedelta(hours=ttl_hours)
        conn.execute(
            "INSERT INTO room_invites (token, room_name, created_by, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (token, room, g.user_id, expires_at.isoformat()),
        )

    return jsonify({
        "token": token,
        "room": room,
        "expires_at": expires_at.isoformat(),
        "ttl_hours": ttl_hours,
        "url": f"/?room={room}&invite={token}",
    }), 201


# ---------------------------------------------------------------------
# Join (invite token or password)
# ---------------------------------------------------------------------
@rooms_bp.route("/<room>/join", methods=["POST"])
@require_auth
@rate_limit(max_calls=20, window_seconds=60)
def join(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    token = data.get("invite")
    password = data.get("password")

    with get_db() as conn:
        row = _get_room(conn, room)
        if not row:
            return jsonify({"error": "Room not registered"}), 404

        if _is_member(conn, room, g.user_id):
            return jsonify({"room": room, "joined": True, "already_member": True})

        if token:
            inv = conn.execute(
                "SELECT * FROM room_invites WHERE token = ? AND room_name = ?",
                (token, room),
            ).fetchone()
            if not inv:
                return jsonify({"error": "Invalid invite"}), 401
            try:
                expires = datetime.fromisoformat(inv["expires_at"])
            except ValueError:
                return jsonify({"error": "Invalid invite expiry"}), 500
            if expires < _now():
                return jsonify({"error": "Invite expired"}), 401
        elif row["password_hash"]:
            if not password or not check_password_hash(row["password_hash"], password):
                return jsonify({"error": "Invalid password"}), 401
        else:
            return jsonify({"error": "Invite required"}), 401

        conn.execute(
            "INSERT INTO room_members (room_name, user_id, role) "
            "VALUES (?, ?, 'member')",
            (room, g.user_id),
        )

    return jsonify({"room": room, "joined": True}), 200


# ---------------------------------------------------------------------
# List my rooms
# ---------------------------------------------------------------------
@rooms_bp.route("", methods=["GET"])
@require_auth
def list_rooms():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT r.name, r.owner_id, r.is_public, r.created_at, "
            "  (SELECT COUNT(*) FROM room_members WHERE room_name = r.name) AS member_count "
            "FROM rooms r "
            "JOIN room_members m ON m.room_name = r.name "
            "WHERE m.user_id = ? "
            "ORDER BY r.name",
            (g.user_id,),
        ).fetchall()
    return jsonify({"rooms": [dict(r) for r in rows]})


# ---------------------------------------------------------------------
# Members (member-only)
# ---------------------------------------------------------------------
@rooms_bp.route("/<room>/members", methods=["GET"])
@require_auth
def list_members(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        if not _get_room(conn, room):
            return jsonify({"error": "Room not registered"}), 404
        if not _is_member(conn, room, g.user_id):
            return jsonify({"error": "Not a member"}), 403

        rows = conn.execute(
            "SELECT u.id, u.username, m.role, m.joined_at "
            "FROM room_members m JOIN users u ON u.id = m.user_id "
            "WHERE m.room_name = ? ORDER BY m.joined_at",
            (room,),
        ).fetchall()
    return jsonify({"members": [dict(r) for r in rows]})


# ---------------------------------------------------------------------
# Kick (owner only)
# ---------------------------------------------------------------------
@rooms_bp.route("/<room>/members/<int:user_id>", methods=["DELETE"])
@require_auth
def kick(room, user_id):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        row = _get_room(conn, room)
        if not row:
            return jsonify({"error": "Room not registered"}), 404
        if row["owner_id"] != g.user_id:
            return jsonify({"error": "Only the owner can kick members"}), 403
        if user_id == g.user_id:
            return jsonify({"error": "Cannot kick yourself"}), 400

        cur = conn.execute(
            "DELETE FROM room_members WHERE room_name = ? AND user_id = ?",
            (room, user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not a member"}), 404
    return jsonify({"kicked": user_id})


# ---------------------------------------------------------------------
# Delete room (owner only)
# ---------------------------------------------------------------------
@rooms_bp.route("/<room>", methods=["DELETE"])
@require_auth
def delete_room(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        row = _get_room(conn, room)
        if not row:
            return jsonify({"error": "Room not registered"}), 404
        if row["owner_id"] != g.user_id:
            return jsonify({"error": "Only the owner can delete the room"}), 403

        conn.execute("DELETE FROM rooms WHERE name = ?", (room,))
        conn.execute("DELETE FROM room_members WHERE room_name = ?", (room,))
        conn.execute("DELETE FROM room_invites WHERE room_name = ?", (room,))
    return jsonify({"deleted": room})
