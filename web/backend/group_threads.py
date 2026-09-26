"""Group message threads (Phase 62).

Single-level replies to messages in a group DM, mirroring the room
chat thread pattern (Phase 33).

Endpoints:
    GET  /api/groups/<id>/messages/<msg_id>/replies
    GET  /api/groups/<id>/messages/<msg_id>/thread     (parent + replies)
"""
from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth

grp_threads_bp = Blueprint("group_threads", __name__, url_prefix="/api/groups")


def _is_member(conn, group_id, user_id):
    return conn.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    ).fetchone() is not None


def _row_to_msg(row):
    d = dict(row)
    d.setdefault("parent_id", None)
    d.setdefault("kind", "text")
    d.setdefault("attachment_id", None)
    d.setdefault("edited_at", None)
    d.setdefault("deleted", 0)
    d.setdefault("read_at", None)
    d.setdefault("reply_count", 0)
    return d


@grp_threads_bp.route("/<int:group_id>/messages/<int:msg_id>/replies", methods=["GET"])
@require_auth
def list_replies(group_id, msg_id):
    with get_db() as conn:
        if not _is_member(conn, group_id, g.user_id):
            return jsonify({"error": "Not a member"}), 403
        parent = conn.execute(
            "SELECT id FROM group_messages WHERE id = ? AND group_id = ?",
            (msg_id, group_id),
        ).fetchone()
        if not parent:
            return jsonify({"error": "Parent not found"}), 404
        try:
            rows = conn.execute("""
                SELECT m.id, m.sender_id, m.body, m.encrypted, m.parent_id,
                       m.kind, m.attachment_id, m.edited_at, m.deleted,
                       m.read_at, m.created_at, u.username AS sender
                FROM group_messages m JOIN users u ON u.id = m.sender_id
                WHERE m.parent_id = ? ORDER BY m.id ASC LIMIT 200
            """, (msg_id,)).fetchall()
        except Exception:
            rows = []
    return jsonify({"parent_id": msg_id, "replies": [_row_to_msg(r) for r in rows]})


@grp_threads_bp.route("/<int:group_id>/messages/<int:msg_id>/thread", methods=["GET"])
@require_auth
def thread_overview(group_id, msg_id):
    """Parent + all replies + reply_count in one call."""
    with get_db() as conn:
        if not _is_member(conn, group_id, g.user_id):
            return jsonify({"error": "Not a member"}), 403
        parent = conn.execute("""
            SELECT m.id, m.sender_id, m.body, m.encrypted, m.parent_id,
                   m.kind, m.attachment_id, m.edited_at, m.deleted,
                   m.read_at, m.created_at, u.username AS sender,
                   (SELECT COUNT(*) FROM group_messages r WHERE r.parent_id = m.id) AS reply_count
            FROM group_messages m JOIN users u ON u.id = m.sender_id
            WHERE m.id = ? AND m.group_id = ?
        """, (msg_id, group_id)).fetchone()
        if not parent:
            return jsonify({"error": "Message not found"}), 404
        try:
            replies = conn.execute("""
                SELECT m.id, m.sender_id, m.body, m.encrypted, m.parent_id,
                       m.kind, m.attachment_id, m.edited_at, m.deleted,
                       m.read_at, m.created_at, u.username AS sender
                FROM group_messages m JOIN users u ON u.id = m.sender_id
                WHERE m.parent_id = ? ORDER BY m.id ASC LIMIT 200
            """, (msg_id,)).fetchall()
        except Exception:
            replies = []

    return jsonify({
        "parent": _row_to_msg(parent),
        "replies": [_row_to_msg(r) for r in replies],
    })
