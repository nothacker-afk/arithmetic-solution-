"""Message forwarding (Phase 86).

Forward a message from any context (room / DM / group) to any other
context the user has access to, preserving attribution.

Endpoint:
    POST /api/forward
        {
          source_kind: "chat" | "dm" | "group",
          source_id: <int>,
          dest_kind: "chat" | "dm" | "group",
          dest_id: <string (room) or int (thread/group)>,
          note: "optional prefix"
        }
"""
from __future__ import annotations
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

fwd_bp = Blueprint("forwarding", __name__, url_prefix="/api/forward")

VALID_KINDS = {"chat", "dm", "group"}
ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MAX_NOTE = 300


def _can_read_source(conn, kind, src_id, user_id):
    if kind == "chat":
        row = conn.execute(
            "SELECT username FROM chat_messages WHERE id = ?", (src_id,)
        ).fetchone()
        return row is not None
    if kind == "dm":
        row = conn.execute("""
            SELECT 1 FROM dm_messages m JOIN dm_threads t ON t.id = m.thread_id
            WHERE m.id = ? AND (t.user_a = ? OR t.user_b = ?)
        """, (src_id, user_id, user_id)).fetchone()
        return row is not None
    if kind == "group":
        row = conn.execute("""
            SELECT 1 FROM group_messages m JOIN group_members gm ON gm.group_id = m.group_id
            WHERE m.id = ? AND gm.user_id = ?
        """, (src_id, user_id)).fetchone()
        return row is not None
    return False


def _can_write_dest(conn, kind, dest_id, user_id):
    if kind == "chat":
        if not isinstance(dest_id, str) or not ROOM_RE.match(dest_id):
            return False
        return True  # rooms are open by default
    if kind == "dm":
        if not isinstance(dest_id, int):
            return False
        row = conn.execute("""
            SELECT 1 FROM dm_threads WHERE id = ? AND (user_a = ? OR user_b = ?)
        """, (dest_id, user_id, user_id)).fetchone()
        return row is not None
    if kind == "group":
        if not isinstance(dest_id, int):
            return False
        row = conn.execute("""
            SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?
        """, (dest_id, user_id)).fetchone()
        return row is not None
    return False


def _load_source(conn, kind, src_id):
    if kind == "chat":
        return conn.execute(
            "SELECT body, encrypted, kind AS msg_kind, attachment_id, username AS sender "
            "FROM chat_messages WHERE id = ?", (src_id,)
        ).fetchone()
    if kind == "dm":
        return conn.execute("""
            SELECT m.body, m.encrypted, m.kind AS msg_kind, m.attachment_id, u.username AS sender
            FROM dm_messages m JOIN users u ON u.id = m.sender_id
            WHERE m.id = ?
        """, (src_id,)).fetchone()
    if kind == "group":
        return conn.execute("""
            SELECT m.body, m.encrypted, m.kind AS msg_kind, m.attachment_id, u.username AS sender
            FROM group_messages m JOIN users u ON u.id = m.sender_id
            WHERE m.id = ?
        """, (src_id,)).fetchone()
    return None


def _insert_dest(conn, kind, dest_id, user_id, body, encrypted, msg_kind, attachment_id):
    """Insert into the destination and return the new message id + sender username."""
    me = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    username = me["username"] if me else "unknown"

    if kind == "chat":
        cur = conn.execute(
            "INSERT INTO chat_messages (room_id, username, body, encrypted, kind, attachment_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (dest_id, username, body, encrypted, msg_kind or "text", attachment_id),
        )
        return cur.lastrowid

    if kind == "dm":
        cur = conn.execute(
            "INSERT INTO dm_messages (thread_id, sender_id, body, encrypted, kind, attachment_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (dest_id, user_id, body, encrypted, msg_kind or "text", attachment_id),
        )
        return cur.lastrowid

    if kind == "group":
        cur = conn.execute(
            "INSERT INTO group_messages (group_id, sender_id, body, encrypted, kind, attachment_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (dest_id, user_id, body, encrypted, msg_kind or "text", attachment_id),
        )
        return cur.lastrowid

    return None


@fwd_bp.route("", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def forward():
    data = request.get_json(silent=True) or {}
    src_kind = (data.get("source_kind") or "").strip().lower()
    dest_kind = (data.get("dest_kind") or "").strip().lower()
    src_id = data.get("source_id")
    dest_id = data.get("dest_id")
    note = (data.get("note") or "").strip()[:MAX_NOTE]

    if src_kind not in VALID_KINDS or dest_kind not in VALID_KINDS:
        return jsonify({"error": f"kinds must be one of {sorted(VALID_KINDS)}"}), 400
    if not isinstance(src_id, int):
        return jsonify({"error": "source_id must be an integer"}), 400

    with get_db() as conn:
        # Authorization
        if not _can_read_source(conn, src_kind, src_id, g.user_id):
            return jsonify({"error": "Cannot read source message"}), 403
        if not _can_write_dest(conn, dest_kind, dest_id, g.user_id):
            return jsonify({"error": "Cannot write to destination"}), 403

        # Load source
        src = _load_source(conn, src_kind, src_id)
        if not src:
            return jsonify({"error": "Source not found"}), 404

        # Build forwarded body
        prefix = f"> Forwarded from **{src['sender']}**"
        if note:
            prefix = f"{note}\n\n{prefix}"
        fwd_body = f"{prefix}\n\n{src['body'] or ''}".strip()

        # Insert into destination with the SAME encryption flag as source
        # (attachments passed through as references)
        new_id = _insert_dest(
            conn,
            dest_kind, dest_id, g.user_id,
            fwd_body,
            src["encrypted"],
            src["msg_kind"],
            src["attachment_id"],
        )

        # Log
        conn.execute("""
            INSERT INTO message_forwards
            (user_id, source_kind, source_id, source_room, dest_kind, dest_id, dest_room, new_message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            g.user_id, src_kind, src_id, None,
            dest_kind, str(dest_id), None, new_id,
        ))

    log_event("message.forward", actor_id=g.user_id, resource="message",
              resource_id=str(src_id),
              details={"dest_kind": dest_kind, "dest_id": str(dest_id)})

    return jsonify({
        "new_message_id": new_id,
        "dest_kind": dest_kind,
        "dest_id": dest_id,
    }), 201


@fwd_bp.route("/history", methods=["GET"])
@require_auth
def history():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, source_kind, source_id, dest_kind, dest_id,
                   new_message_id, created_at
            FROM message_forwards
            WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 100
        """, (g.user_id,)).fetchall()
    return jsonify({"forwards": [dict(r) for r in rows]})
