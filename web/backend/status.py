"""User status (Phase 55).

Endpoints:
    GET  /api/status/me              my status
    PUT  /api/status/me              {state, emoji?, message?}
    GET  /api/status/user/<username> another user's status
    GET  /api/status/users?ids=1,2   batch
"""
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

status_bp = Blueprint("status", __name__, url_prefix="/api/status")

VALID_STATES = {"available", "away", "busy", "dnd", "invisible"}
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")


def _status_row_to_dict(row):
    if not row:
        return {"state": "available", "emoji": None, "message": None}
    return {
        "state": row["state"],
        "emoji": row["emoji"],
        "message": row["message"],
        "updated_at": row["updated_at"],
    }


@status_bp.route("/me", methods=["GET"])
@require_auth
def get_me():
    with get_db() as conn:
        row = conn.execute(
            "SELECT state, emoji, message, updated_at FROM user_status WHERE user_id = ?",
            (g.user_id,),
        ).fetchone()
    return jsonify(_status_row_to_dict(row))


@status_bp.route("/me", methods=["PUT"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def set_me():
    data = request.get_json(silent=True) or {}
    state = (data.get("state") or "available").lower()
    if state not in VALID_STATES:
        return jsonify({"error": f"state must be one of {sorted(VALID_STATES)}"}), 400
    emoji = (data.get("emoji") or "").strip()[:8] or None
    message = (data.get("message") or "").strip()[:80] or None

    with get_db() as conn:
        conn.execute("""
            INSERT INTO user_status (user_id, state, emoji, message, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                state = excluded.state,
                emoji = excluded.emoji,
                message = excluded.message,
                updated_at = CURRENT_TIMESTAMP
        """, (g.user_id, state, emoji, message))

    # Broadcast
    try:
        from .realtime import socketio
        me = None
        with get_db() as conn:
            me = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
        if me:
            socketio.emit("user_status", {
                "user_id": g.user_id,
                "username": me["username"],
                "state": state, "emoji": emoji, "message": message,
            }, broadcast=True)
    except Exception:
        pass

    return jsonify({"state": state, "emoji": emoji, "message": message})


@status_bp.route("/user/<username>", methods=["GET"])
@require_auth
def get_user_status(username):
    if not USERNAME_RE.match(username or ""):
        return jsonify({"error": "Invalid username"}), 400
    with get_db() as conn:
        u = conn.execute("SELECT id, username FROM users WHERE username = ?",
                         (username,)).fetchone()
        if not u:
            return jsonify({"error": "User not found"}), 404
        row = conn.execute(
            "SELECT state, emoji, message, updated_at FROM user_status WHERE user_id = ?",
            (u["id"],),
        ).fetchone()
    out = _status_row_to_dict(row)
    out["username"] = u["username"]
    return jsonify(out)


@status_bp.route("/users", methods=["GET"])
@require_auth
def batch_status():
    ids_raw = request.args.get("ids") or ""
    try:
        ids = [int(x) for x in ids_raw.split(",") if x.strip()]
    except ValueError:
        return jsonify({"error": "invalid ids"}), 400
    if not ids:
        return jsonify({"statuses": {}})
    if len(ids) > 100:
        return jsonify({"error": "max 100 ids"}), 400

    placeholders = ",".join("?" for _ in ids)
    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT s.user_id, u.username, s.state, s.emoji, s.message
            FROM user_status s JOIN users u ON u.id = s.user_id
            WHERE s.user_id IN ({placeholders})
        """, tuple(ids)).fetchall()
        known = {r["user_id"]: dict(r) for r in rows}

    out = {}
    for uid in ids:
        out[str(uid)] = known.get(uid, {"user_id": uid, "state": "available",
                                        "emoji": None, "message": None})
    return jsonify({"statuses": out})
