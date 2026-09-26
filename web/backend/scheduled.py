"""Scheduled messages (Phase 46).

Users queue a message for future delivery. A background dispatcher
(runs every SCHEDULER_INTERVAL_SECONDS, default 30s) picks up due
messages, inserts them into chat_messages, and broadcasts over WS.

Endpoints:
    POST   /api/scheduled             {room_id, body, send_at, kind?, attachment_id?, encrypted?}
    GET    /api/scheduled             list my pending scheduled messages
    DELETE /api/scheduled/<id>        cancel one
"""
import re
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

scheduled_bp = Blueprint("scheduled", __name__, url_prefix="/api/scheduled")

MAX_BODY_BYTES = 4096
SCHED_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _parse_iso(s: str):
    """Parse an ISO timestamp (with or without Z). Returns tz-aware or None."""
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


@_scheduled_bp.route("", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def schedule():
    data = request.get_json(silent=True) or {}
    room_id = (data.get("room_id") or "").strip()
    body = data.get("body") or ""
    send_at_raw = data.get("send_at")
    kind = (data.get("kind") or "text").strip()[:16]
    attachment_id = data.get("attachment_id")
    encrypted = 1 if data.get("encrypted") else 0

    if not room_id:
        return jsonify({"error": "room_id required"}), 400
    if not isinstance(body, str):
        return jsonify({"error": "body must be a string"}), 400
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        return jsonify({"error": "Message too long"}), 400
    if kind == "text" and not body.strip():
        return jsonify({"error": "body required"}), 400

    send_at = _parse_iso(send_at_raw)
    if not send_at:
        return jsonify({"error": "send_at must be an ISO timestamp"}), 400

    now = datetime.now(timezone.utc)
    if send_at <= now:
        return jsonify({"error": "send_at must be in the future"}), 400
    if (send_at - now).total_seconds() > 365 * 24 * 3600:
        return jsonify({"error": "send_at must be within 1 year"}), 400

    sched_id = uuid.uuid4().hex
    with get_db() as conn:
        me = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
        sender_username = me["username"] if me else "unknown"
        conn.execute(
            "INSERT INTO scheduled_messages "
            "(id, room_id, sender_id, sender_username, body, encrypted, "
            " kind, attachment_id, send_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sched_id, room_id, g.user_id, sender_username, body, encrypted,
             kind, attachment_id, send_at.isoformat()),
        )
    return jsonify({
        "id": sched_id,
        "room_id": room_id,
        "send_at": send_at.isoformat(),
        "body": body,
        "kind": kind,
    }), 201


@scheduled_bp.route("", methods=["GET"])
@require_auth
def list_scheduled():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, room_id, body, kind, attachment_id, send_at, encrypted, created_at
            FROM scheduled_messages
            WHERE sender_id = ? AND sent = 0
            ORDER BY send_at ASC
        """, (g.user_id,)).fetchall()
    return jsonify({"pending": [dict(r) for r in rows]})


@scheduled_bp.route("/<sched_id>", methods=["DELETE"])
@require_auth
def cancel(sched_id):
    if not SCHED_ID_RE.match(sched_id):
        return jsonify({"error": "Invalid id"}), 400
    with get_db() as conn:
        row = conn.execute(
            "SELECT sender_id, sent FROM scheduled_messages WHERE id = ?", (sched_id,),
        ).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if row["sender_id"] != g.user_id:
            return jsonify({"error": "Not yours"}), 403
        if row["sent"]:
            return jsonify({"error": "Already sent"}), 400
        conn.execute("DELETE FROM scheduled_messages WHERE id = ?", (sched_id,))
    return jsonify({"cancelled": sched_id})


# ---------------------------------------------------------------------
# Dispatcher — called by jobs.py and directly testable
# ---------------------------------------------------------------------
def dispatch_due(now=None) -> int:
    """Insert any due scheduled messages. Returns count dispatched."""
    if now is None:
        now = datetime.now(timezone.utc)
    now_iso = now.isoformat(timespec="seconds")

    sent = 0
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM scheduled_messages
            WHERE sent = 0 AND send_at <= ?
            ORDER BY send_at ASC LIMIT 100
        """, (now_iso,)).fetchall()

        for r in rows:
            cur = conn.execute(
                "INSERT INTO chat_messages "
                "(room_id, username, body, encrypted, kind, attachment_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (r["room_id"], r["sender_username"], r["body"],
                 r["encrypted"], r["kind"], r["attachment_id"]),
            )
            msg_id = cur.lastrowid
            conn.execute(
                "UPDATE scheduled_messages SET sent = 1, sent_message_id = ? "
                "WHERE id = ?", (msg_id, r["id"]),
            )
            sent += 1

            # Best-effort broadcast
            try:
                from .realtime import socketio
                socketio.emit("chat_message", {
                    "id": msg_id,
                    "username": r["sender_username"],
                    "body": r["body"],
                    "encrypted": bool(r["encrypted"]),
                    "kind": r["kind"],
                    "scheduled": True,
                }, to=r["room_id"])
            except Exception:
                pass

    return sent
