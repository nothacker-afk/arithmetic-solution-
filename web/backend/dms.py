"""Encrypted user-to-user direct messages.

Endpoints:
    GET    /api/dms/threads                                    list my threads
    POST   /api/dms/threads                    {username}      start/fetch thread
    GET    /api/dms/threads/<id>?limit=50                      messages
    POST   /api/dms/threads/<id>               {body,encrypted,kind,attachment_id}
    DELETE /api/dms/threads/<id>                               delete thread
    PATCH  /api/dms/threads/<id>/messages/<mid>  {body}        edit
    DELETE /api/dms/threads/<id>/messages/<mid>                soft-delete
    GET    /api/dms/threads/<id>/messages/<mid>/edits          edit history
    GET    /api/dms/threads/<id>/ttl                           get TTL
    PUT    /api/dms/threads/<id>/ttl              {ttl_seconds} set TTL
"""
from flask import Blueprint, request, jsonify, g

from .auth import require_auth
from .database import get_db
from .rate_limit import rate_limit
from .audit import log_event
from .contacts import is_blocked_either

dms_bp = Blueprint("dms", __name__, url_prefix="/api/dms")

MAX_BODY_BYTES = 8192
MAX_PREVIEW = 80


def _row_to_dict(row):
    d = dict(row)
    d.setdefault("kind", "text")
    d.setdefault("attachment_id", None)
    d.setdefault("edited_at", None)
    d.setdefault("deleted", 0)
    d.setdefault("expires_at", None)
    d.setdefault("read_at", None)
    return d


def _thread_ttl_seconds(conn, thread_id):
    row = conn.execute(
        "SELECT ttl_seconds FROM thread_ttls WHERE thread_id = ?", (thread_id,)
    ).fetchone()
    return int(row["ttl_seconds"]) if row else 0


def _find_user(conn, username):
    return conn.execute(
        "SELECT id, username FROM users WHERE username = ?", (username,)
    ).fetchone()


def _get_or_create_thread(conn, uid_a, uid_b):
    a, b = sorted([uid_a, uid_b])
    row = conn.execute(
        "SELECT id FROM dm_threads WHERE user_a = ? AND user_b = ?", (a, b),
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO dm_threads (user_a, user_b) VALUES (?, ?)", (a, b),
    )
    return cur.lastrowid


# ---------------------------------------------------------------------
# List my threads
# ---------------------------------------------------------------------
@dms_bp.route("/threads", methods=["GET"])
@require_auth
def list_threads():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT t.id, t.last_message_at,
                   CASE WHEN t.user_a = ? THEN t.user_b ELSE t.user_a END AS other_id,
                   (SELECT COUNT(*) FROM dm_messages
                      WHERE thread_id = t.id AND sender_id != ? AND read_at IS NULL
                   ) AS unread
            FROM dm_threads t
            WHERE t.user_a = ? OR t.user_b = ?
            ORDER BY COALESCE(t.last_message_at, t.created_at) DESC
        """, (g.user_id, g.user_id, g.user_id, g.user_id)).fetchall()

        threads = []
        for t in rows:
            other = conn.execute("SELECT username FROM users WHERE id = ?",
                                 (t["other_id"],)).fetchone()
            threads.append({
                "id": t["id"],
                "other_username": other["username"] if other else "[deleted]",
                "last_message_at": t["last_message_at"],
                "unread": t["unread"],
            })
    return jsonify({"threads": threads})


# ---------------------------------------------------------------------
# Start or fetch a thread
# ---------------------------------------------------------------------
@dms_bp.route("/threads", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def start_thread():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "username is required"}), 400

    with get_db() as conn:
        me = conn.execute("SELECT username FROM users WHERE id = ?",
                          (g.user_id,)).fetchone()
        if me and me["username"] == username:
            return jsonify({"error": "Cannot DM yourself"}), 400
        other = _find_user(conn, username)
        if not other:
            return jsonify({"error": "User not found"}), 404
        if is_blocked_either(g.user_id, other["id"]):
            return jsonify({"error": "Cannot start a conversation with this user"}), 403
        thread_id = _get_or_create_thread(conn, g.user_id, other["id"])
    return jsonify({"thread_id": thread_id, "other_username": username}), 201


# ---------------------------------------------------------------------
# List messages in a thread
# ---------------------------------------------------------------------
@dms_bp.route("/threads/<int:thread_id>", methods=["GET"])
@require_auth
def list_messages(thread_id):
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except ValueError:
        limit = 50

    with get_db() as conn:
        t = conn.execute("SELECT user_a, user_b FROM dm_threads WHERE id = ?",
                         (thread_id,)).fetchone()
        if not t:
            return jsonify({"error": "Thread not found"}), 404
        if g.user_id not in (t["user_a"], t["user_b"]):
            return jsonify({"error": "Not a participant"}), 403

        # Mark as read
        conn.execute(
            "UPDATE dm_messages SET read_at = CURRENT_TIMESTAMP "
            "WHERE thread_id = ? AND sender_id != ? AND read_at IS NULL",
            (thread_id, g.user_id),
        )

        rows = conn.execute("""
            SELECT m.id, m.sender_id, m.body, m.encrypted, m.kind,
                   m.attachment_id, m.edited_at, m.deleted, m.expires_at,
                   m.read_at, m.created_at, u.username AS sender
            FROM dm_messages m JOIN users u ON u.id = m.sender_id
            WHERE m.thread_id = ? ORDER BY m.id DESC LIMIT ?
        """, (thread_id, limit)).fetchall()

        other_id = t["user_b"] if t["user_a"] == g.user_id else t["user_a"]
        other = conn.execute("SELECT username FROM users WHERE id = ?",
                             (other_id,)).fetchone()
        me = conn.execute("SELECT username FROM users WHERE id = ?",
                          (g.user_id,)).fetchone()

    return jsonify({
        "thread_id": thread_id,
        "messages": [_row_to_dict(r) for r in reversed(rows)],
        "participants": {
            "me": me["username"] if me else "",
            "other": other["username"] if other else "",
        },
        "other_user_id": other_id,
    })


# ---------------------------------------------------------------------
# Send a message
# ---------------------------------------------------------------------
@dms_bp.route("/threads/<int:thread_id>", methods=["POST"])
@require_auth
@rate_limit(max_calls=60, window_seconds=60)
def send_message(thread_id):
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
        t = conn.execute("SELECT user_a, user_b FROM dm_threads WHERE id = ?",
                         (thread_id,)).fetchone()
        if not t:
            return jsonify({"error": "Thread not found"}), 404
        if g.user_id not in (t["user_a"], t["user_b"]):
            return jsonify({"error": "Not a participant"}), 403

        # Phase 41: block enforcement
        other_id = t["user_b"] if t["user_a"] == g.user_id else t["user_a"]
        if is_blocked_either(g.user_id, other_id):
            return jsonify({"error": "Blocked — cannot send messages"}), 403

        ttl = _thread_ttl_seconds(conn, thread_id)

        cur = conn.execute(
            "INSERT INTO dm_messages "
            "(thread_id, sender_id, body, encrypted, kind, attachment_id, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, "
            "  CASE WHEN ? > 0 THEN datetime('now', '+' || ? || ' seconds') ELSE NULL END)",
            (thread_id, g.user_id, body, 1 if encrypted else 0,
             kind, attachment_id, ttl, ttl),
        )
        msg_id = cur.lastrowid

        conn.execute(
            "UPDATE dm_threads SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?",
            (thread_id,),
        )

        row = conn.execute("""
            SELECT m.id, m.sender_id, m.body, m.encrypted, m.kind,
                   m.attachment_id, m.edited_at, m.deleted, m.expires_at,
                   m.read_at, m.created_at, u.username AS sender
            FROM dm_messages m JOIN users u ON u.id = m.sender_id
            WHERE m.id = ?
        """, (msg_id,)).fetchone()

        other_id = t["user_b"] if t["user_a"] == g.user_id else t["user_a"]
        me = conn.execute("SELECT username FROM users WHERE id = ?",
                          (g.user_id,)).fetchone()

    log_event("dm.send", actor_id=g.user_id, resource="thread",
              resource_id=str(thread_id))

    try:
        from .notifications import send_push
        preview = "[encrypted]" if encrypted else body[:MAX_PREVIEW]
        send_push(
            other_id,
            f"New DM from {me['username'] if me else 'someone'}",
            preview,
            {"kind": "dm", "thread_id": str(thread_id)},
        )
    except Exception:
        pass

    return jsonify(_row_to_dict(row)), 201


# ---------------------------------------------------------------------
# Delete thread
# ---------------------------------------------------------------------
@dms_bp.route("/threads/<int:thread_id>", methods=["DELETE"])
@require_auth
def delete_thread(thread_id):
    with get_db() as conn:
        t = conn.execute("SELECT user_a, user_b FROM dm_threads WHERE id = ?",
                         (thread_id,)).fetchone()
        if not t:
            return jsonify({"error": "Thread not found"}), 404
        if g.user_id not in (t["user_a"], t["user_b"]):
            return jsonify({"error": "Not a participant"}), 403
        conn.execute("DELETE FROM dm_messages WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM dm_threads WHERE id = ?", (thread_id,))
    return jsonify({"deleted": thread_id})


# ---------------------------------------------------------------------
# Edit message
# ---------------------------------------------------------------------
@dms_bp.route("/threads/<int:thread_id>/messages/<int:msg_id>", methods=["PATCH"])
@require_auth
def edit_dm(thread_id, msg_id):
    data = request.get_json(silent=True) or {}
    new_body = (data.get("body") or "").strip()
    if not new_body:
        return jsonify({"error": "body required"}), 400
    if len(new_body.encode("utf-8")) > MAX_BODY_BYTES:
        return jsonify({"error": "Message too long"}), 400

    with get_db() as conn:
        t = conn.execute("SELECT user_a, user_b FROM dm_threads WHERE id = ?",
                         (thread_id,)).fetchone()
        if not t:
            return jsonify({"error": "Thread not found"}), 404
        if g.user_id not in (t["user_a"], t["user_b"]):
            return jsonify({"error": "Not a participant"}), 403

        row = conn.execute(
            "SELECT sender_id, body FROM dm_messages WHERE id = ? AND thread_id = ?",
            (msg_id, thread_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Message not found"}), 404
        if row["sender_id"] != g.user_id:
            return jsonify({"error": "Only the sender can edit"}), 403

        conn.execute(
            "INSERT INTO message_edits (message_kind, message_id, old_body, edited_by) "
            "VALUES ('dm', ?, ?, ?)",
            (msg_id, row["body"], g.user_id),
        )
        conn.execute(
            "UPDATE dm_messages SET body = ?, edited_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_body, msg_id),
        )
        updated = conn.execute(
            "SELECT id, sender_id, body, encrypted, kind, attachment_id, "
            "       edited_at, deleted, expires_at, read_at, created_at "
            "FROM dm_messages WHERE id = ?", (msg_id,),
        ).fetchone()

    return jsonify(_row_to_dict(updated))


# ---------------------------------------------------------------------
# Soft-delete message
# ---------------------------------------------------------------------
@dms_bp.route("/threads/<int:thread_id>/messages/<int:msg_id>", methods=["DELETE"])
@require_auth
def delete_dm(thread_id, msg_id):
    with get_db() as conn:
        t = conn.execute("SELECT user_a, user_b FROM dm_threads WHERE id = ?",
                         (thread_id,)).fetchone()
        if not t:
            return jsonify({"error": "Thread not found"}), 404
        if g.user_id not in (t["user_a"], t["user_b"]):
            return jsonify({"error": "Not a participant"}), 403

        row = conn.execute(
            "SELECT sender_id FROM dm_messages WHERE id = ? AND thread_id = ?",
            (msg_id, thread_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Message not found"}), 404
        if row["sender_id"] != g.user_id:
            return jsonify({"error": "Only the sender can delete"}), 403

        conn.execute(
            "UPDATE dm_messages SET deleted = 1, body = '', "
            "attachment_id = NULL, edited_at = CURRENT_TIMESTAMP WHERE id = ?",
            (msg_id,),
        )

    return jsonify({"deleted": msg_id, "tombstone": True})


# ---------------------------------------------------------------------
# Edit history
# ---------------------------------------------------------------------
@dms_bp.route("/threads/<int:thread_id>/messages/<int:msg_id>/edits", methods=["GET"])
@require_auth
def get_dm_edits(thread_id, msg_id):
    with get_db() as conn:
        t = conn.execute("SELECT user_a, user_b FROM dm_threads WHERE id = ?",
                         (thread_id,)).fetchone()
        if not t or g.user_id not in (t["user_a"], t["user_b"]):
            return jsonify({"error": "Not found"}), 404
        rows = conn.execute(
            "SELECT old_body, created_at FROM message_edits "
            "WHERE message_kind = 'dm' AND message_id = ? ORDER BY id DESC",
            (msg_id,),
        ).fetchall()
    return jsonify({"edits": [dict(r) for r in rows]})


# ---------------------------------------------------------------------
# Thread TTL
# ---------------------------------------------------------------------
@dms_bp.route("/threads/<int:thread_id>/ttl", methods=["GET"])
@require_auth
def get_thread_ttl(thread_id):
    with get_db() as conn:
        t = conn.execute("SELECT user_a, user_b FROM dm_threads WHERE id = ?",
                         (thread_id,)).fetchone()
        if not t or g.user_id not in (t["user_a"], t["user_b"]):
            return jsonify({"error": "Not found"}), 404
        ttl = _thread_ttl_seconds(conn, thread_id)
    return jsonify({"thread_id": thread_id, "ttl_seconds": ttl})


@dms_bp.route("/threads/<int:thread_id>/ttl", methods=["PUT"])
@require_auth
def set_thread_ttl(thread_id):
    data = request.get_json(silent=True) or {}
    try:
        ttl = int(data.get("ttl_seconds", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "ttl_seconds must be an integer"}), 400
    if ttl < 0 or ttl > 30 * 24 * 3600:
        return jsonify({"error": "ttl_seconds must be 0..2592000"}), 400
    with get_db() as conn:
        t = conn.execute("SELECT user_a, user_b FROM dm_threads WHERE id = ?",
                         (thread_id,)).fetchone()
        if not t or g.user_id not in (t["user_a"], t["user_b"]):
            return jsonify({"error": "Not found"}), 404
        if ttl == 0:
            conn.execute("DELETE FROM thread_ttls WHERE thread_id = ?", (thread_id,))
        else:
            conn.execute(
                "INSERT INTO thread_ttls (thread_id, ttl_seconds) VALUES (?, ?) "
                "ON CONFLICT(thread_id) DO UPDATE SET ttl_seconds = excluded.ttl_seconds, "
                "updated_at = CURRENT_TIMESTAMP",
                (thread_id, ttl),
            )
    return jsonify({"thread_id": thread_id, "ttl_seconds": ttl})
