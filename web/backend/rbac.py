"""Advanced RBAC (Phase 76).

Room-scoped custom roles with fine-grained permissions. When no role
is assigned, falls back to owner check + no extra permissions.

Permissions (all boolean):
    can_post                — send messages in the room
    can_pin                 — pin messages
    can_delete_others       — soft-delete other people's messages
    can_manage_wiki         — create/edit/delete wiki pages
    can_kick                — remove members from the room
    can_ban                 — reserved for future use
    can_manage_roles        — create/edit roles
    can_archive             — create archives

Endpoints:
    GET    /api/rooms/<room>/roles                     list roles + my permissions
    POST   /api/rooms/<room>/roles                     {name, permissions[]}
    DELETE /api/rooms/<room>/roles/<name>
    POST   /api/rooms/<room>/roles/<name>/assign       {username}
    DELETE /api/rooms/<room>/roles/<name>/assign/<username>
    GET    /api/rooms/<room>/permissions/<username>    effective permissions
"""
import json
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

rbac_bp = Blueprint("rbac", __name__, url_prefix="/api/rooms")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")

ALL_PERMISSIONS = {
    "can_post",
    "can_pin",
    "can_delete_others",
    "can_manage_wiki",
    "can_kick",
    "can_ban",
    "can_manage_roles",
    "can_archive",
}


def _validate_room(room):
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


def _is_owner(conn, room, user_id):
    row = conn.execute("SELECT owner_id FROM rooms WHERE name = ?", (room,)).fetchone()
    return row and row["owner_id"] == user_id


# ---------------------------------------------------------------------
# Permission resolution
# ---------------------------------------------------------------------
def effective_permissions(conn, room: str, user_id: int) -> dict:
    """Return the effective permission set for a user in a room."""
    owner = _is_owner(conn, room, user_id)

    # Owner implicitly has everything
    if owner:
        return {p: True for p in ALL_PERMISSIONS}

    # Look up assigned role
    row = conn.execute("""
        SELECT r.permissions
        FROM room_role_assignments a
        JOIN room_roles r ON r.room_id = a.room_id AND r.name = a.role_name
        WHERE a.room_id = ? AND a.user_id = ?
    """, (room, user_id)).fetchone()

    base = {p: False for p in ALL_PERMISSIONS}
    if row:
        try:
            granted = set(json.loads(row["permissions"]))
            for p in granted:
                if p in base:
                    base[p] = True
        except Exception:
            pass
    return base


def has_permission(conn, room: str, user_id: int, permission: str) -> bool:
    """Public helper for other modules (bulk_ops, wiki, etc.)."""
    if permission not in ALL_PERMISSIONS:
        return False
    return effective_permissions(conn, room, user_id).get(permission, False)


def require_permission(conn, room: str, user_id: int, permission: str):
    """Raise PermissionError if not allowed."""
    if not has_permission(conn, room, user_id, permission):
        raise PermissionError(f"Missing permission: {permission}")


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------
@rbac_bp.route("/<room>/roles", methods=["GET"])
@require_auth
def list_roles(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        rows = conn.execute("""
            SELECT name, permissions, created_at,
                   (SELECT COUNT(*) FROM room_role_assignments
                    WHERE room_id = ? AND role_name = room_roles.name) AS member_count
            FROM room_roles WHERE room_id = ?
            ORDER BY name
        """, (room, room)).fetchall()

        roles = []
        for r in rows:
            d = dict(r)
            try:
                d["permissions"] = json.loads(d["permissions"])
            except Exception:
                d["permissions"] = []
            roles.append(d)

        my = effective_permissions(conn, room, g.user_id)
        is_owner = _is_owner(conn, room, g.user_id)

    return jsonify({
        "room": room,
        "roles": roles,
        "my_permissions": my,
        "is_owner": bool(is_owner),
    })


@rbac_bp.route("/<room>/roles", methods=["POST"])
@require_auth
@rate_limit(max_calls=20, window_seconds=60)
def create_or_update_role(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip().lower()
    perms = data.get("permissions") or []

    if not NAME_RE.match(name):
        return jsonify({"error": "name must be 2-32 chars: a-z, 0-9, _, -"}), 400
    if not isinstance(perms, list):
        return jsonify({"error": "permissions must be a list"}), 400
    unknown = set(perms) - ALL_PERMISSIONS
    if unknown:
        return jsonify({"error": f"unknown permissions: {sorted(unknown)}"}), 400

    with get_db() as conn:
        if not _is_owner(conn, room, g.user_id) and not has_permission(
                conn, room, g.user_id, "can_manage_roles"):
            return jsonify({"error": "Permission denied"}), 403

        conn.execute("""
            INSERT INTO room_roles (room_id, name, permissions, created_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(room_id, name) DO UPDATE SET
                permissions = excluded.permissions
        """, (room, name, json.dumps(sorted(perms)), g.user_id))

    log_event("rbac.role.set", actor_id=g.user_id, resource="room",
              resource_id=room, details={"role": name, "permissions": perms})

    return jsonify({"room": room, "name": name, "permissions": perms}), 201


@rbac_bp.route("/<room>/roles/<name>", methods=["DELETE"])
@require_auth
def delete_role(room, name):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        if not _is_owner(conn, room, g.user_id):
            return jsonify({"error": "Only the owner can delete roles"}), 403
        cur = conn.execute("DELETE FROM room_roles WHERE room_id = ? AND name = ?",
                           (room, name))
        if cur.rowcount == 0:
            return jsonify({"error": "Role not found"}), 404
        conn.execute("DELETE FROM room_role_assignments WHERE room_id = ? AND role_name = ?",
                     (room, name))
    return jsonify({"deleted": name})


@rbac_bp.route("/<room>/roles/<name>/assign", methods=["POST"])
@require_auth
def assign_role(room, name):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "username required"}), 400

    with get_db() as conn:
        if not _is_owner(conn, room, g.user_id) and not has_permission(
                conn, room, g.user_id, "can_manage_roles"):
            return jsonify({"error": "Permission denied"}), 403

        role = conn.execute(
            "SELECT 1 FROM room_roles WHERE room_id = ? AND name = ?", (room, name),
        ).fetchone()
        if not role:
            return jsonify({"error": "Role not found"}), 404

        u = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not u:
            return jsonify({"error": "User not found"}), 404

        member = conn.execute(
            "SELECT 1 FROM room_members WHERE room_name = ? AND user_id = ?",
            (room, u["id"]),
        ).fetchone()
        if not member:
            return jsonify({"error": "User is not a member of the room"}), 400

        conn.execute("""
            INSERT INTO room_role_assignments (room_id, user_id, role_name, assigned_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(room_id, user_id) DO UPDATE SET
                role_name = excluded.role_name,
                assigned_at = CURRENT_TIMESTAMP,
                assigned_by = excluded.assigned_by
        """, (room, u["id"], name, g.user_id))

    log_event("rbac.assign", actor_id=g.user_id, resource="room",
              resource_id=room, details={"role": name, "user": username})
    return jsonify({"room": room, "username": username, "role": name}), 201


@rbac_bp.route("/<room>/roles/<name>/assign/<username>", methods=["DELETE"])
@require_auth
def unassign_role(room, name, username):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        if not _is_owner(conn, room, g.user_id) and not has_permission(
                conn, room, g.user_id, "can_manage_roles"):
            return jsonify({"error": "Permission denied"}), 403
        u = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not u:
            return jsonify({"error": "User not found"}), 404
        cur = conn.execute(
            "DELETE FROM room_role_assignments "
            "WHERE room_id = ? AND user_id = ? AND role_name = ?",
            (room, u["id"], name),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Assignment not found"}), 404
    return jsonify({"removed": True})


@rbac_bp.route("/<room>/permissions/<username>", methods=["GET"])
@require_auth
def get_permissions(room, username):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        u = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not u:
            return jsonify({"error": "User not found"}), 404
        return jsonify({
            "room": room,
            "username": username,
            "permissions": effective_permissions(conn, room, u["id"]),
        })


@rbac_bp.route("/permissions/available", methods=["GET"])
def available_permissions():
    return jsonify({"permissions": sorted(ALL_PERMISSIONS)})
