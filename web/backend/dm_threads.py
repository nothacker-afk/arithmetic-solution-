"""Threaded DM replies (Phase 82).

Single-level replies within direct messages, mirroring the chat
(Phase 33) and group (Phase 62) thread patterns.

Endpoints:
    GET  /api/dms/threads/<tid>/messages/<mid>/replies
    GET  /api/dms/threads/<tid>/messages/<mid>/thread
"""
from __future__ import annotations
from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth

dm_threads_bp = Blueprint("dm_threads", __name__, url_prefix="/api/dms")


def _is_participant(conn, thread_id, user_id):
    row = conn.execute(
        "SELECT user_a, user_b FROM dm_threads WHERE id = ?", (thread_id,)
    ).fetchone()
    if not row:
        return False
    return user_id in (row["user_a"], row["user_b"])


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


@dm_threads_bp.route("/threads/<int:thread_id>/messages/<int:msg_id>/replies", methods=["GET"])
@require_auth
def list_replies(thread_id, msg_id):
    with get_db() as conn:
        if not _is_participant(conn, thread_id, g.user_id):
            return jsonify({"error": "Not a participant"}), 403
        parent = conn.execute(
            "SELECT id FROM dm_messages WHERE id = ? AND thread_id = ?",
            (msg_id, thread_id),
        ).fetchone()
        if not parent:
            return jsonify({"error": "Parent not found"}), 404
        try:
            rows = conn.execute("""
                SELECT m.id, m.sender_id, m.body, m.encrypted, m.parent_id,
                       m.kind, m.attachment_id, m.edited_at, m.deleted,
                       m.read_at, m.created_at, u.username AS sender
                FROM dm_messages m JOIN users u ON u.id = m.sender_id
                WHERE m.parent_id = ? ORDER BY m.id ASC LIMIT 200
            """, (msg_id,)).fetchall()
        except Exception:
            rows = []
    return jsonify({"parent_id": msg_id, "replies": [_row_to_msg(r) for r in rows]})


@dm_threads_bp.route("/threads/<int:thread_id>/messages/<int:msg_id>/thread", methods=["GET"])
@require_auth
def thread_overview(thread_id, msg_id):
    """Parent + all replies + reply_count in one call."""
    with get_db() as conn:
        if not _is_participant(conn, thread_id, g.user_id):
            return jsonify({"error": "Not a participant"}), 403
        parent = conn.execute("""
            SELECT m.id, m.sender_id, m.body, m.encrypted, m.parent_id,
                   m.kind, m.attachment_id, m.edited_at, m.deleted,
                   m.read_at, m.created_at, u.username AS sender,
                   (SELECT COUNT(*) FROM dm_messages r WHERE r.parent_id = m.id) AS reply_count
            FROM dm_messages m JOIN users u ON u.id = m.sender_id
            WHERE m.id = ? AND m.thread_id = ?
        """, (msg_id, thread_id)).fetchone()
        if not parent:
            return jsonify({"error": "Message not found"}), 404
        try:
            replies = conn.execute("""
                SELECT m.id, m.sender_id, m.body, m.encrypted, m.parent_id,
                       m.kind, m.attachment_id, m.edited_at, m.deleted,
                       m.read_at, m.created_at, u.username AS sender
                FROM dm_messages m JOIN users u ON u.id = m.sender_id
                WHERE m.parent_id = ? ORDER BY m.id ASC LIMIT 200
            """, (msg_id,)).fetchall()
        except Exception:
            replies = []

    return jsonify({
        "parent": _row_to_msg(parent),
        "replies": [_row_to_msg(r) for r in replies],
    })
