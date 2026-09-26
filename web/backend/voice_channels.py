"""Voice channels (Phase 53).

Persistent presence layer for always-on audio rooms. Actual audio
flows peer-to-peer via WebRTC — the server tracks who's in which
channel so clients know who to connect to.

Endpoints:
    GET    /api/rooms/<room>/voice_channels             list channels + occupants
    POST   /api/rooms/<room>/voice_channels/join        {channel, muted?}
    POST   /api/rooms/<room>/voice_channels/leave       {channel}
    POST   /api/rooms/<room>/voice_channels/mute        {channel, muted}
    POST   /api/rooms/<room>/voice_channels/ping        {channel}
"""
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

vc_bp = Blueprint("voice_channels", __name__, url_prefix="/api/rooms")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
CHANNEL_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")
DEFAULT_CHANNELS = ["main", "afk", "music"]


def _validate_room(room):
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


def _validate_channel(channel):
    if not CHANNEL_RE.match(channel or ""):
        raise ValueError("Invalid channel name")
    return channel


@vc_bp.route("/<room>/voice_channels", methods=["GET"])
@require_auth
def list_channels(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        rows = conn.execute("""
            SELECT channel, user_id, username, muted, joined_at
            FROM voice_channel_presence WHERE room_id = ?
            ORDER BY channel, joined_at
        """, (room,)).fetchall()

    # Group by channel; ensure all default channels appear even if empty
    channels = {name: [] for name in DEFAULT_CHANNELS}
    for r in rows:
        ch = r["channel"]
        channels.setdefault(ch, []).append({
            "user_id": r["user_id"],
            "username": r["username"],
            "muted": bool(r["muted"]),
            "joined_at": r["joined_at"],
        })

    return jsonify({
        "room": room,
        "channels": [
            {"name": name, "members": members}
            for name, members in channels.items()
        ],
    })


@vc_bp.route("/<room>/voice_channels/join", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def join(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    data = request.get_json(silent=True) or {}
    try:
        channel = _validate_channel((data.get("channel") or "main").strip())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    muted = 1 if data.get("muted") else 0

    with get_db() as conn:
        me = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
        username = me["username"] if me else "guest"
        # Leave any other channel in this room first
        conn.execute(
            "DELETE FROM voice_channel_presence WHERE room_id = ? AND user_id = ?",
            (room, g.user_id),
        )
        conn.execute("""
            INSERT INTO voice_channel_presence (room_id, channel, user_id, username, muted)
            VALUES (?, ?, ?, ?, ?)
        """, (room, channel, g.user_id, username, muted))

    # Broadcast
    try:
        from .realtime import socketio
        socketio.emit("voice_joined", {
            "room": room, "channel": channel,
            "user_id": g.user_id, "username": username, "muted": bool(muted),
        }, to=room)
    except Exception:
        pass

    return jsonify({"room": room, "channel": channel, "username": username}), 201


@vc_bp.route("/<room>/voice_channels/leave", methods=["POST"])
@require_auth
def leave(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        me = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
        cur = conn.execute(
            "DELETE FROM voice_channel_presence WHERE room_id = ? AND user_id = ?",
            (room, g.user_id),
        )
    if cur.rowcount:
        try:
            from .realtime import socketio
            socketio.emit("voice_left", {
                "room": room,
                "user_id": g.user_id,
                "username": (me["username"] if me else "guest"),
            }, to=room)
        except Exception:
            pass
    return jsonify({"left": cur.rowcount})


@vc_bp.route("/<room>/voice_channels/mute", methods=["POST"])
@require_auth
def set_mute(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    data = request.get_json(silent=True) or {}
    muted = 1 if data.get("muted") else 0
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE voice_channel_presence SET muted = ? WHERE room_id = ? AND user_id = ?",
            (muted, room, g.user_id),
        )
    if cur.rowcount:
        try:
            from .realtime import socketio
            socketio.emit("voice_mute", {
                "room": room, "user_id": g.user_id, "muted": bool(muted),
            }, to=room)
        except Exception:
            pass
    return jsonify({"muted": bool(muted), "updated": cur.rowcount})


@vc_bp.route("/<room>/voice_channels/ping", methods=["POST"])
@require_auth
def ping(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        conn.execute(
            "UPDATE voice_channel_presence SET last_ping = CURRENT_TIMESTAMP "
            "WHERE room_id = ? AND user_id = ?", (room, g.user_id),
        )
    return jsonify({"ok": True})


# ---------------------------------------------------------------------
# Presence cleanup — called from jobs.run_retention()
# ---------------------------------------------------------------------
def purge_stale_presence(max_idle_seconds: int = 90) -> int:
    """Drop presence rows that haven't pinged recently."""
    with get_db() as conn:
        cur = conn.execute("""
            DELETE FROM voice_channel_presence
            WHERE last_ping < datetime('now', '-' || ? || ' seconds')
        """, (max_idle_seconds,))
        return cur.rowcount
