"""Contact book + block list (Phase 41).

Endpoints:
    GET    /api/contacts                     list my contacts
    POST   /api/contacts                     {username, nickname?}
    DELETE /api/contacts/<user_id>           remove contact
    PUT    /api/contacts/<user_id>/favourite {favourite: bool}
    GET    /api/blocks                       list my blocks
    POST   /api/blocks                       {username, reason?}
    DELETE /api/blocks/<user_id>             unblock
"""
from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

contacts_bp = Blueprint("contacts", __name__, url_prefix="/api")


def _find_user(conn, username):
    return conn.execute(
        "SELECT id, username FROM users WHERE username = ?", (username,)
    ).fetchone()


def is_blocked(a_id, b_id) -> bool:
    """Return True if a_id has blocked b_id."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM blocks WHERE blocker_id = ? AND blocked_id = ?",
            (a_id, b_id),
        ).fetchone()
    return row is not None


def is_blocked_either(a_id, b_id) -> bool:
    """Return True if either side has blocked the other."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM blocks "
            "WHERE (blocker_id = ? AND blocked_id = ?) "
            "   OR (blocker_id = ? AND blocked_id = ?)",
            (a_id, b_id, b_id, a_id),
        ).fetchone()
    return row is not None


# ---------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------
@contacts_bp.route("/contacts", methods=["GET"])
@require_auth
def list_contacts():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT c.contact_user_id, u.username, c.favourite, c.nickname,
                   c.created_at,
                   (SELECT COUNT(*) FROM dm_threads t
                    WHERE (t.user_a = ? AND t.user_b = c.contact_user_id)
                       OR (t.user_b = ? AND t.user_a = c.contact_user_id)
                   ) AS shared_threads
            FROM contacts c JOIN users u ON u.id = c.contact_user_id
            WHERE c.user_id = ?
            ORDER BY c.favourite DESC, u.username
        """, (g.user_id, g.user_id, g.user_id)).fetchall()
    return jsonify({"contacts": [dict(r) for r in rows]})


@contacts_bp.route("/contacts", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def add_contact():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    nickname = (data.get("nickname") or "").strip()[:64] or None
    if not username:
        return jsonify({"error": "username is required"}), 400

    with get_db() as conn:
        me = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
        if me and me["username"] == username:
            return jsonify({"error": "Cannot add yourself"}), 400
        other = _find_user(conn, username)
        if not other:
            return jsonify({"error": "User not found"}), 404

        try:
            conn.execute(
                "INSERT INTO contacts (user_id, contact_user_id, nickname) "
                "VALUES (?, ?, ?)",
                (g.user_id, other["id"], nickname),
            )
        except Exception:
            # UNIQUE — already a contact; treat as idempotent
            return jsonify({
                "contact_user_id": other["id"],
                "username": other["username"],
                "already": True,
            }), 200

    log_event("contact.add", actor_id=g.user_id, resource="user",
              resource_id=str(other["id"]))
    return jsonify({
        "contact_user_id": other["id"],
        "username": other["username"],
        "nickname": nickname,
        "favourite": 0,
    }), 201


@contacts_bp.route("/contacts/<int:user_id>", methods=["DELETE"])
@require_auth
def remove_contact(user_id):
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM contacts WHERE user_id = ? AND contact_user_id = ?",
            (g.user_id, user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not a contact"}), 404
    return jsonify({"removed": user_id})


@contacts_bp.route("/contacts/<int:user_id>/favourite", methods=["PUT"])
@require_auth
def set_favourite(user_id):
    data = request.get_json(silent=True) or {}
    fav = 1 if data.get("favourite") else 0
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE contacts SET favourite = ? "
            "WHERE user_id = ? AND contact_user_id = ?",
            (fav, g.user_id, user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not a contact"}), 404
    return jsonify({"contact_user_id": user_id, "favourite": fav})


# ---------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------
@contacts_bp.route("/blocks", methods=["GET"])
@require_auth
def list_blocks():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT b.blocked_id, u.username, b.reason, b.created_at
            FROM blocks b JOIN users u ON u.id = b.blocked_id
            WHERE b.blocker_id = ?
            ORDER BY b.created_at DESC
        """, (g.user_id,)).fetchall()
    return jsonify({"blocks": [dict(r) for r in rows]})


@contacts_bp.route("/blocks", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def add_block():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    reason = (data.get("reason") or "").strip()[:200] or None
    if not username:
        return jsonify({"error": "username is required"}), 400

    with get_db() as conn:
        other = _find_user(conn, username)
        if not other:
            return jsonify({"error": "User not found"}), 404
        if other["id"] == g.user_id:
            return jsonify({"error": "Cannot block yourself"}), 400
        try:
            conn.execute(
                "INSERT INTO blocks (blocker_id, blocked_id, reason) VALUES (?, ?, ?)",
                (g.user_id, other["id"], reason),
            )
        except Exception:
            return jsonify({
                "blocked_id": other["id"],
                "username": other["username"],
                "already": True,
            }), 200

    log_event("block.add", actor_id=g.user_id, resource="user",
              resource_id=str(other["id"]), details={"reason": reason})
    return jsonify({
        "blocked_id": other["id"],
        "username": other["username"],
        "reason": reason,
    }), 201


@contacts_bp.route("/blocks/<int:user_id>", methods=["DELETE"])
@require_auth
def unblock(user_id):
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM blocks WHERE blocker_id = ? AND blocked_id = ?",
            (g.user_id, user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not blocked"}), 404
    log_event("block.remove", actor_id=g.user_id, resource="user",
              resource_id=str(user_id))
    return jsonify({"removed": user_id})
