"""Multi-device sync (Phase 67).

Each device gets a stable id (client-generated). The server tracks:
    - which devices a user has
    - the last-synced read cursor per device / room
    - aggregated sync state per user

Endpoints:
    POST   /api/sync/devices/register          {device_id, label?, platform?}
    GET    /api/sync/devices                    list my devices
    DELETE /api/sync/devices/<device_id>        remove a device
    POST   /api/sync/read-state                 {device_id, room_id, last_read_message_id}
    GET    /api/sync/read-state?device_id=&room_id=
    GET    /api/sync/aggregate?room_id=         aggregated across devices
"""
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

sync_bp = Blueprint("sync", __name__, url_prefix="/api/sync")

DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@sync_bp.route("/devices/register", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def register_device():
    data = request.get_json(silent=True) or {}
    device_id = (data.get("device_id") or "").strip()
    label = (data.get("label") or "").strip()[:64] or None
    platform = (data.get("platform") or "unknown").strip()[:32]

    if not DEVICE_ID_RE.match(device_id):
        return jsonify({"error": "device_id must be 8-64 chars (a-z, A-Z, 0-9, _, -)"}), 400

    with get_db() as conn:
        conn.execute("""
            INSERT INTO device_sync_state (user_id, device_id, label, platform)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, device_id) DO UPDATE SET
                label = COALESCE(excluded.label, device_sync_state.label),
                platform = excluded.platform,
                last_seen_at = CURRENT_TIMESTAMP
        """, (g.user_id, device_id, label, platform))

    return jsonify({"device_id": device_id, "label": label, "platform": platform}), 201


@sync_bp.route("/devices", methods=["GET"])
@require_auth
def list_devices():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT device_id, label, platform, last_sync_at, last_seen_at
            FROM device_sync_state WHERE user_id = ?
            ORDER BY last_seen_at DESC
        """, (g.user_id,)).fetchall()
    return jsonify({"devices": [dict(r) for r in rows]})


@sync_bp.route("/devices/<device_id>", methods=["DELETE"])
@require_auth
def remove_device(device_id):
    if not DEVICE_ID_RE.match(device_id or ""):
        return jsonify({"error": "Invalid device id"}), 400
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM device_sync_state WHERE user_id = ? AND device_id = ?",
            (g.user_id, device_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not found"}), 404
        # Also clear its read state
        conn.execute(
            "DELETE FROM device_read_state WHERE user_id = ? AND device_id = ?",
            (g.user_id, device_id),
        )
    return jsonify({"deleted": device_id})


@sync_bp.route("/read-state", methods=["POST"])
@require_auth
@rate_limit(max_calls=120, window_seconds=60)
def set_read_state():
    data = request.get_json(silent=True) or {}
    device_id = (data.get("device_id") or "").strip()
    room_id = (data.get("room_id") or "").strip()
    last_id = data.get("last_read_message_id")

    if not DEVICE_ID_RE.match(device_id):
        return jsonify({"error": "Invalid device_id"}), 400
    if not ROOM_RE.match(room_id):
        return jsonify({"error": "Invalid room_id"}), 400
    if not isinstance(last_id, int) or last_id < 0:
        return jsonify({"error": "last_read_message_id must be >= 0"}), 400

    with get_db() as conn:
        # Check for regression
        existing = conn.execute(
            "SELECT last_read_message_id FROM device_read_state "
            "WHERE user_id = ? AND device_id = ? AND room_id = ?",
            (g.user_id, device_id, room_id),
        ).fetchone()
        if existing and existing["last_read_message_id"] >= last_id:
            return jsonify({
                "no_change": True,
                "last_read_message_id": existing["last_read_message_id"],
            })
        conn.execute("""
            INSERT INTO device_read_state
            (user_id, device_id, room_id, last_read_message_id, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, device_id, room_id) DO UPDATE SET
                last_read_message_id = excluded.last_read_message_id,
                updated_at = CURRENT_TIMESTAMP
        """, (g.user_id, device_id, room_id, last_id))
        # Touch device last-sync
        conn.execute(
            "UPDATE device_sync_state SET last_sync_at = CURRENT_TIMESTAMP "
            "WHERE user_id = ? AND device_id = ?",
            (g.user_id, device_id),
        )
    return jsonify({"room_id": room_id, "device_id": device_id,
                    "last_read_message_id": last_id})


@sync_bp.route("/read-state", methods=["GET"])
@require_auth
def get_read_state():
    device_id = (request.args.get("device_id") or "").strip()
    room_id = (request.args.get("room_id") or "").strip()
    where = ["user_id = ?"]
    params = [g.user_id]
    if device_id:
        where.append("device_id = ?"); params.append(device_id)
    if room_id:
        where.append("room_id = ?"); params.append(room_id)

    with get_db() as conn:
        rows = conn.execute(
            f"SELECT device_id, room_id, last_read_message_id, updated_at "
            f"FROM device_read_state WHERE {' AND '.join(where)} "
            f"ORDER BY updated_at DESC LIMIT 200",
            tuple(params),
        ).fetchall()
    return jsonify({"states": [dict(r) for r in rows]})


@sync_bp.route("/aggregate", methods=["GET"])
@require_auth
def aggregate():
    """For a given room, aggregate the last-read cursor across all my devices."""
    room_id = (request.args.get("room_id") or "").strip()
    if not ROOM_RE.match(room_id):
        return jsonify({"error": "room_id required"}), 400

    with get_db() as conn:
        row = conn.execute("""
            SELECT MAX(last_read_message_id) AS max_read,
                   MIN(last_read_message_id) AS min_read,
                   COUNT(DISTINCT device_id) AS device_count
            FROM device_read_state
            WHERE user_id = ? AND room_id = ?
        """, (g.user_id, room_id)).fetchone()
        devices = conn.execute("""
            SELECT device_id, last_read_message_id, updated_at
            FROM device_read_state
            WHERE user_id = ? AND room_id = ?
            ORDER BY updated_at DESC
        """, (g.user_id, room_id)).fetchall()

    return jsonify({
        "room_id": room_id,
        "max_read": row["max_read"] or 0,
        "min_read": row["min_read"] or 0,
        "device_count": row["device_count"] or 0,
        "per_device": [dict(d) for d in devices],
    })
