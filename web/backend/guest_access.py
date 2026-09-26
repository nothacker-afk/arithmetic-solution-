"""Guest access links (Phase 65).

Owners can mint tokens that let guests join a room without an account.
Tokens can have an expiry and a use limit.

Endpoints (authenticated):
    POST   /api/rooms/<room>/guest_tokens    {label?, expires_in_hours?, max_uses?, allow_write?}
    GET    /api/rooms/<room>/guest_tokens    list tokens for a room
    DELETE /api/guest_tokens/<token>         revoke

Endpoints (unauthenticated):
    GET    /api/guest/<token>                inspect token (room name, allow_write)
    POST   /api/guest/<token>/redeem         record usage + return room info
"""
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

guest_bp = Blueprint("guest_access", __name__, url_prefix="/api")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")


def _validate_room(room):
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


def _now():
    return datetime.now(timezone.utc)


def _expired(expires_at: str) -> bool:
    if not expires_at:
        return False
    try:
        e = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if e.tzinfo is None:
            e = e.replace(tzinfo=timezone.utc)
        return e < _now()
    except Exception:
        return False


@guest_bp.route("/rooms/<room>/guest_tokens", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def create_token(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    label = (data.get("label") or "").strip()[:80] or None
    allow_write = 1 if data.get("allow_write") else 0

    try:
        expires_in = int(data.get("expires_in_hours", 24 * 7))
    except (TypeError, ValueError):
        expires_in = 24 * 7
    if expires_in < 1 or expires_in > 24 * 90:
        return jsonify({"error": "expires_in_hours must be 1..2160"}), 400

    max_uses = data.get("max_uses")
    if max_uses is not None:
        try:
            max_uses = int(max_uses)
        except (TypeError, ValueError):
            return jsonify({"error": "max_uses must be an integer"}), 400
        if max_uses < 1 or max_uses > 1000:
            return jsonify({"error": "max_uses must be 1..1000"}), 400

    with get_db() as conn:
        r = conn.execute("SELECT owner_id FROM rooms WHERE name = ?", (room,)).fetchone()
        if not r:
            return jsonify({"error": "Room not registered"}), 404
        if r["owner_id"] != request.user_id if hasattr(request, "user_id") else False:
            pass
        # We need the user id from require_auth — use g
        from flask import g
        if r["owner_id"] != g.user_id:
            return jsonify({"error": "Only the room owner can create guest tokens"}), 403

        token = secrets.token_urlsafe(32)
        expires_at = (_now() + timedelta(hours=expires_in)).isoformat(timespec="seconds")
        conn.execute("""
            INSERT INTO guest_access_tokens
            (token, room_id, created_by, label, expires_at, uses_remaining, allow_write)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (token, room, g.user_id, label, expires_at, max_uses, allow_write))

    log_event("guest_token.create", actor_id=g.user_id, resource="guest_token",
              resource_id=token[:8] + "…", details={"room": room, "label": label})

    return jsonify({
        "token": token,
        "room": room,
        "label": label,
        "expires_at": expires_at,
        "uses_remaining": max_uses,
        "allow_write": bool(allow_write),
        "url": f"/?guest={token}",
    }), 201


@guest_bp.route("/rooms/<room>/guest_tokens", methods=["GET"])
@require_auth
def list_tokens(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    from flask import g
    with get_db() as conn:
        r = conn.execute("SELECT owner_id FROM rooms WHERE name = ?", (room,)).fetchone()
        if not r or r["owner_id"] != g.user_id:
            return jsonify({"error": "Only the room owner can list tokens"}), 403
        rows = conn.execute("""
            SELECT token, label, expires_at, uses_remaining, use_count,
                   allow_write, created_at
            FROM guest_access_tokens WHERE room_id = ?
            ORDER BY created_at DESC
        """, (room,)).fetchall()

    out = []
    for row in rows:
        d = dict(row)
        d["expired"] = _expired(d["expires_at"])
        d["token_prefix"] = d["token"][:8] + "…"
        d.pop("token")  # don't leak full tokens after creation
        out.append(d)
    return jsonify({"tokens": out})


@guest_bp.route("/guest_tokens/<token>", methods=["DELETE"])
@require_auth
def revoke_token(token):
    if not TOKEN_RE.match(token or ""):
        return jsonify({"error": "Invalid token"}), 400
    from flask import g
    with get_db() as conn:
        row = conn.execute(
            "SELECT room_id, created_by FROM guest_access_tokens WHERE token = ?", (token,),
        ).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if row["created_by"] != g.user_id:
            return jsonify({"error": "Not yours"}), 403
        conn.execute("DELETE FROM guest_access_tokens WHERE token = ?", (token,))
    log_event("guest_token.revoke", actor_id=g.user_id, resource="guest_token",
              resource_id=token[:8] + "…")
    return jsonify({"revoked": True})


@guest_bp.route("/guest/<token>", methods=["GET"])
def inspect_token(token):
    if not TOKEN_RE.match(token or ""):
        return jsonify({"error": "Invalid token"}), 400
    with get_db() as conn:
        row = conn.execute("""
            SELECT g.room_id, g.label, g.expires_at, g.uses_remaining, g.allow_write,
                   r.owner_id
            FROM guest_access_tokens g
            LEFT JOIN rooms r ON r.name = g.room_id
            WHERE g.token = ?
        """, (token,)).fetchone()
        if not row:
            return jsonify({"error": "Token not found"}), 404
        if _expired(row["expires_at"]):
            return jsonify({"error": "Token expired", "expired": True}), 410
        if row["uses_remaining"] is not None and row["uses_remaining"] <= 0:
            return jsonify({"error": "Token exhausted", "exhausted": True}), 410
        room_name = row["room_id"]

    return jsonify({
        "room": room_name,
        "label": row["label"],
        "allow_write": bool(row["allow_write"]),
        "expires_at": row["expires_at"],
        "uses_remaining": row["uses_remaining"],
    })


@guest_bp.route("/guest/<token>/redeem", methods=["POST"])
@rate_limit(max_calls=20, window_seconds=60)
def redeem_token(token):
    if not TOKEN_RE.match(token or ""):
        return jsonify({"error": "Invalid token"}), 400
    with get_db() as conn:
        row = conn.execute("""
            SELECT room_id, expires_at, uses_remaining, allow_write, use_count
            FROM guest_access_tokens WHERE token = ?
        """, (token,)).fetchone()
        if not row:
            return jsonify({"error": "Token not found"}), 404
        if _expired(row["expires_at"]):
            return jsonify({"error": "Token expired"}), 410
        if row["uses_remaining"] is not None and row["uses_remaining"] <= 0:
            return jsonify({"error": "Token exhausted"}), 410
        new_remaining = (
            row["uses_remaining"] - 1 if row["uses_remaining"] is not None else None
        )
        conn.execute("""
            UPDATE guest_access_tokens
            SET uses_remaining = ?, use_count = use_count + 1
            WHERE token = ?
        """, (new_remaining, token))

    return jsonify({
        "room": row["room_id"],
        "allow_write": bool(row["allow_write"]),
        "uses_remaining": new_remaining,
        "granted": True,
    })
