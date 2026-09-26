"""Room events / calendar (Phase 54).

Endpoints:
    GET    /api/rooms/<room>/events              list upcoming + past
    POST   /api/rooms/<room>/events              {title, starts_at, ...}
    GET    /api/rooms/<room>/events/<id>         single event + RSVPs
    PUT    /api/rooms/<room>/events/<id>         edit
    DELETE /api/rooms/<room>/events/<id>         delete
    POST   /api/rooms/<room>/events/<id>/rsvp    {status: going|maybe|no}
"""
import re
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

events_bp = Blueprint("events", __name__, url_prefix="/api/rooms")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
EVENT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
VALID_RSVP = {"going", "maybe", "no"}


def _validate_room(room):
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


def _parse_iso(s):
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


@events_bp.route("/<room>/events", methods=["GET"])
@require_auth
def list_events(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_db() as conn:
        rows = conn.execute("""
            SELECT e.id, e.title, e.description, e.starts_at, e.ends_at,
                   e.all_day, e.location, e.created_at,
                   u.username AS created_by,
                   (SELECT COUNT(*) FROM room_event_rsvps WHERE event_id = e.id AND status = 'going') AS going_count
            FROM room_events e LEFT JOIN users u ON u.id = e.created_by
            WHERE e.room_id = ?
            ORDER BY e.starts_at ASC
        """, (room,)).fetchall()

    upcoming, past = [], []
    for r in rows:
        d = dict(r)
        (past if (d["starts_at"] or "") < now_iso else upcoming).append(d)

    return jsonify({"room": room, "upcoming": upcoming, "past": past})


@events_bp.route("/<room>/events", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def create_event(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()[:200]
    starts_at = _parse_iso(data.get("starts_at"))
    ends_at = _parse_iso(data.get("ends_at"))
    all_day = 1 if data.get("all_day") else 0
    description = (data.get("description") or "").strip()[:2000] or None
    location = (data.get("location") or "").strip()[:200] or None

    if not title:
        return jsonify({"error": "title required"}), 400
    if not starts_at:
        return jsonify({"error": "starts_at must be an ISO timestamp"}), 400
    if ends_at and ends_at <= starts_at:
        return jsonify({"error": "ends_at must be after starts_at"}), 400

    event_id = uuid.uuid4().hex
    with get_db() as conn:
        conn.execute("""
            INSERT INTO room_events
            (id, room_id, title, description, starts_at, ends_at, all_day, location, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (event_id, room, title, description,
              starts_at.isoformat(), ends_at.isoformat() if ends_at else None,
              all_day, location, g.user_id))

    log_event("event.create", actor_id=g.user_id, resource="event",
              resource_id=event_id, details={"room": room, "title": title})
    return jsonify({
        "id": event_id, "room": room, "title": title,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat() if ends_at else None,
        "all_day": all_day, "description": description, "location": location,
    }), 201


@events_bp.route("/<room>/events/<event_id>", methods=["GET"])
@require_auth
def get_event(room, event_id):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not EVENT_ID_RE.match(event_id):
        return jsonify({"error": "Invalid id"}), 400

    with get_db() as conn:
        row = conn.execute("""
            SELECT e.*, u.username AS created_by_username
            FROM room_events e LEFT JOIN users u ON u.id = e.created_by
            WHERE e.id = ? AND e.room_id = ?
        """, (event_id, room)).fetchone()
        if not row:
            return jsonify({"error": "Event not found"}), 404
        rs = conn.execute("""
            SELECT r.status, u.username
            FROM room_event_rsvps r JOIN users u ON u.id = r.user_id
            WHERE r.event_id = ?
        """, (event_id,)).fetchall()

    out = dict(row)
    out["rsvps"] = [dict(r) for r in rs]
    return jsonify(out)


@events_bp.route("/<room>/events/<event_id>", methods=["PUT"])
@require_auth
def update_event(room, event_id):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not EVENT_ID_RE.match(event_id):
        return jsonify({"error": "Invalid id"}), 400

    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        row = conn.execute(
            "SELECT created_by FROM room_events WHERE id = ? AND room_id = ?",
            (event_id, room),
        ).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if row["created_by"] != g.user_id:
            return jsonify({"error": "Only the creator can edit"}), 403

        sets, params = [], []
        if "title" in data:
            sets.append("title = ?"); params.append((data.get("title") or "").strip()[:200])
        if "description" in data:
            sets.append("description = ?"); params.append((data.get("description") or "").strip()[:2000] or None)
        if "location" in data:
            sets.append("location = ?"); params.append((data.get("location") or "").strip()[:200] or None)
        if "starts_at" in data:
            dt = _parse_iso(data.get("starts_at"))
            if not dt:
                return jsonify({"error": "invalid starts_at"}), 400
            sets.append("starts_at = ?"); params.append(dt.isoformat())
        if "ends_at" in data:
            dt = _parse_iso(data.get("ends_at")) if data.get("ends_at") else None
            sets.append("ends_at = ?"); params.append(dt.isoformat() if dt else None)
        if "all_day" in data:
            sets.append("all_day = ?"); params.append(1 if data.get("all_day") else 0)

        if not sets:
            return jsonify({"error": "nothing to update"}), 400
        params.extend([event_id, room])
        conn.execute(f"UPDATE room_events SET {', '.join(sets)} WHERE id = ? AND room_id = ?", tuple(params))
        updated = conn.execute("SELECT * FROM room_events WHERE id = ?", (event_id,)).fetchone()

    return jsonify(dict(updated))


@events_bp.route("/<room>/events/<event_id>", methods=["DELETE"])
@require_auth
def delete_event(room, event_id):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not EVENT_ID_RE.match(event_id):
        return jsonify({"error": "Invalid id"}), 400

    with get_db() as conn:
        row = conn.execute(
            "SELECT created_by FROM room_events WHERE id = ? AND room_id = ?",
            (event_id, room),
        ).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if row["created_by"] != g.user_id:
            return jsonify({"error": "Only the creator can delete"}), 403
        conn.execute("DELETE FROM room_event_rsvps WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM room_events WHERE id = ?", (event_id,))

    log_event("event.delete", actor_id=g.user_id, resource="event", resource_id=event_id)
    return jsonify({"deleted": event_id})


@events_bp.route("/<room>/events/<event_id>/rsvp", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def rsvp(room, event_id):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not EVENT_ID_RE.match(event_id):
        return jsonify({"error": "Invalid id"}), 400

    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "going").lower()
    if status not in VALID_RSVP:
        return jsonify({"error": f"status must be one of {sorted(VALID_RSVP)}"}), 400

    with get_db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM room_events WHERE id = ? AND room_id = ?",
            (event_id, room),
        ).fetchone()
        if not exists:
            return jsonify({"error": "Event not found"}), 404
        conn.execute("""
            INSERT INTO room_event_rsvps (event_id, user_id, status)
            VALUES (?, ?, ?)
            ON CONFLICT(event_id, user_id) DO UPDATE SET status = excluded.status
        """, (event_id, g.user_id, status))

    return jsonify({"event_id": event_id, "status": status})
