"""Group DMs (Phase 56).

Multi-user conversations. Distinct from 1:1 DMs (dms.py).

Endpoints:
    GET    /api/groups                          list my groups
    POST   /api/groups                          {name, usernames[]}
    GET    /api/groups/<id>                     group + members
    POST   /api/groups/<id>/members             {username}
    DELETE /api/groups/<id>/members/<user_id>   remove member
    GET    /api/groups/<id>/messages            messages
    POST   /api/groups/<id>/messages            {body, encrypted?, kind?}
"""
from flask import Blueprint, request, jsonify, g

from .auth import require_auth
from .database import get_db
from .rate_limit import rate_limit
from .audit import log_event

groups_bp = Blueprint("groups", __name__, url_prefix="/api/groups")

MAX_BODY_BYTES = 8192
MAX_MEMBERS = 50
MAX_NAME = 80


def _row_to_msg(row):
    d = dict(row)
    d.setdefault("kind", "text")
    d.setdefault("attachment_id", None)
    d.setdefault("edited_at", None)
    d.setdefault("deleted", 0)
    d.setdefault("read_at", None)
    return d


def _is_member(conn, group_id, user_id):
    return conn.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    ).fetchone() is not None


def _find_user(conn, username):
    return conn.execute(
        "SELECT id, username FROM users WHERE username = ?", (username,)
    ).fetchone()


# ---------------------------------------------------------------------
# List groups
# ---------------------------------------------------------------------
@groups_bp.route("", methods=["GET"])
@require_auth
def list_groups():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT t.id, t.name, t.last_message_at, t.created_at,
                   (SELECT COUNT(*) FROM group_members WHERE group_id = t.id) AS member_count,
                   (SELECT COUNT(*) FROM group_messages
                      WHERE group_id = t.id AND sender_id != ? AND read_at IS NULL) AS unread
            FROM group_threads t
            JOIN group_members m ON m.group_id = t.id
            WHERE m.user_id = ?
            ORDER BY COALESCE(t.last_message_at, t.created_at) DESC
        """, (g.user_id, g.user_id)).fetchall()
    return jsonify({"groups": [dict(r) for r in rows]})


# ---------------------------------------------------------------------
# Create group
# ---------------------------------------------------------------------
@groups_bp.route("", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def create_group():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()[:MAX_NAME]
    usernames = data.get("usernames") or []
    if not name:
        return jsonify({"error": "name required"}), 400
    if not isinstance(usernames, list):
        return jsonify({"error": "usernames must be a list"}), 400
    if len(usernames) + 1 > MAX_MEMBERS:
        return jsonify({"error": f"too many members (max {MAX_MEMBERS})"}), 400

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO group_threads (name, created_by) VALUES (?, ?)",
            (name, g.user_id),
        )
        group_id = cur.lastrowid
        conn.execute(
            "INSERT INTO group_members (group_id, user_id, role) VALUES (?, ?, 'owner')",
            (group_id, g.user_id),
        )
        added = []
        for u in usernames:
            u = (u or "").strip()
            if not u:
                continue
            other = _find_user(conn, u)
            if other and other["id"] != g.user_id:
                try:
                    conn.execute(
                        "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                        (group_id, other["id"]),
                    )
                    added.append(u)
                except Exception:
                    pass

    log_event("group.create", actor_id=g.user_id, resource="group",
              resource_id=str(group_id), details={"name": name, "members": added})
    return jsonify({"id": group_id, "name": name, "members_added": added}), 201


# ---------------------------------------------------------------------
# Get group + members
# ---------------------------------------------------------------------
@groups_bp.route("/<int:group_id>", methods=["GET"])
@require_auth
def get_group(group_id):
    with get_db() as conn:
        if not _is_member(conn, group_id, g.user_id):
            return jsonify({"error": "Not a member"}), 403
        row = conn.execute(
            "SELECT id, name, created_by, created_at, last_message_at "
            "FROM group_threads WHERE id = ?", (group_id,),
        ).fetchone()
        if not row:
            return jsonify({"error": "Group not found"}), 404
        members = conn.execute("""
            SELECT m.user_id, u.username, m.role, m.joined_at
            FROM group_members m JOIN users u ON u.id = m.user_id
            WHERE m.group_id = ? ORDER BY m.joined_at
        """, (group_id,)).fetchall()
    return jsonify({"group": dict(row), "members": [dict(m) for m in members]})


# ---------------------------------------------------------------------
# Add/remove members
# ---------------------------------------------------------------------
@groups_bp.route("/<int:group_id>/members", methods=["POST"])
@require_auth
def add_member(group_id):
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "username required"}), 400

    with get_db() as conn:
        if not _is_member(conn, group_id, g.user_id):
            return jsonify({"error": "Not a member"}), 403
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM group_members WHERE group_id = ?", (group_id,),
        ).fetchone()["n"]
        if count >= MAX_MEMBERS:
            return jsonify({"error": f"member limit reached ({MAX_MEMBERS})"}), 409
        other = _find_user(conn, username)
        if not other:
            return jsonify({"error": "User not found"}), 404
        try:
            conn.execute(
                "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                (group_id, other["id"]),
            )
        except Exception:
            return jsonify({"error": "Already a member"}), 409
    return jsonify({"group_id": group_id, "added": username}), 201


@groups_bp.route("/<int:group_id>/members/<int:user_id>", methods=["DELETE"])
@require_auth
def remove_member(group_id, user_id):
    with get_db() as conn:
        if not _is_member(conn, group_id, g.user_id):
            return jsonify({"error": "Not a member"}), 403
        # Members can remove themselves; only owner can remove others
        me = conn.execute(
            "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, g.user_id),
        ).fetchone()
        if user_id != g.user_id and (not me or me["role"] != "owner"):
            return jsonify({"error": "Only the owner can remove other members"}), 403
        cur = conn.execute(
            "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not a member"}), 404
    return jsonify({"removed": user_id})


# ---------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------
@groups_bp.route("/<int:group_id>/messages", methods=["GET"])
@require_auth
def list_messages(group_id):
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except ValueError:
        limit = 50

    with get_db() as conn:
        if not _is_member(conn, group_id, g.user_id):
            return jsonify({"error": "Not a member"}), 403

        conn.execute("""
            UPDATE group_messages SET read_at = CURRENT_TIMESTAMP
            WHERE group_id = ? AND sender_id != ? AND read_at IS NULL
        """, (group_id, g.user_id))

        rows = conn.execute("""
            SELECT m.id, m.sender_id, m.body, m.encrypted, m.kind,
                   m.attachment_id, m.edited_at, m.deleted, m.read_at,
                   m.created_at, u.username AS sender
            FROM group_messages m JOIN users u ON u.id = m.sender_id
            WHERE m.group_id = ? ORDER BY m.id DESC LIMIT ?
        """, (group_id, limit)).fetchall()

    return jsonify({
        "group_id": group_id,
        "messages": [_row_to_msg(r) for r in reversed(rows)],
    })


@groups_bp.route("/<int:group_id>/messages", methods=["POST"])
@require_auth
@rate_limit(max_calls=60, window_seconds=60)
def send_message(group_id):
    data = request.get_json(silent=True) or {}
    body = data.get("body") or ""
    encrypted = bool(data.get("encrypted", True))
    kind = (data.get("kind") or "text").strip()[:16]
    attachment_id = data.get("attachment_id")

    if not isinstance(body, str):
        return jsonify({"error": "body must be a string"}), 400
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        return jsonify({"error": "Message too long"}), 400
    if kind == "text" and not body.strip():
        return jsonify({"error": "body required"}), 400

    with get_db() as conn:
        if not _is_member(conn, group_id, g.user_id):
            return jsonify({"error": "Not a member"}), 403

        cur = conn.execute(
            "INSERT INTO group_messages "
            "(group_id, sender_id, body, encrypted, kind, attachment_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (group_id, g.user_id, body, 1 if encrypted else 0, kind, attachment_id),
        )
        msg_id = cur.lastrowid
        conn.execute(
            "UPDATE group_threads SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?",
            (group_id,),
        )
        row = conn.execute("""
            SELECT m.id, m.sender_id, m.body, m.encrypted, m.kind, m.attachment_id,
                   m.edited_at, m.deleted, m.read_at, m.created_at,
                   u.username AS sender
            FROM group_messages m JOIN users u ON u.id = m.sender_id
            WHERE m.id = ?
        """, (msg_id,)).fetchone()

    # Broadcast over WebSocket
    try:
        from .realtime import socketio
        socketio.emit("group_message", {
            "group_id": group_id,
            "id": msg_id,
            "sender": row["sender"] if row else "?",
            "body": body,
            "encrypted": encrypted,
            "kind": kind,
        }, to=f"group_{group_id}")
    except Exception:
        pass

    return jsonify(_row_to_msg(row)), 201
