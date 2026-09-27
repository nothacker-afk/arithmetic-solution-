"""Event reminders (Phase 73).

Users can register to be reminded N minutes before a room event.
A background tick (called from the workspace scheduler) checks due
reminders and dispatches push notifications via Phase 19.

Endpoints:
    GET    /api/rooms/<room>/events/<event_id>/reminders      my reminders
    POST   /api/rooms/<room>/events/<event_id>/reminders      {minutes_before}
    DELETE /api/rooms/<room>/events/<event_id>/reminders/<minutes>
"""
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .datetime_utils import parse_iso

rm_bp = Blueprint("event_reminders", __name__, url_prefix="/api/rooms")

EVENT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
ALLOWED_MINUTES = [5, 10, 15, 30, 60, 120, 1440]


def _validate_room(room):
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


def _validate_event_id(eid):
    if not EVENT_ID_RE.match(eid or ""):
        raise ValueError("Invalid event id")
    return eid


@rm_bp.route("/<room>/events/<event_id>/reminders", methods=["GET"])
@require_auth
def list_reminders(room, event_id):
    try:
        room = _validate_room(room)
        event_id = _validate_event_id(event_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        # Sanity: event must belong to room
        ev = conn.execute(
            "SELECT 1 FROM room_events WHERE id = ? AND room_id = ?",
            (event_id, room),
        ).fetchone()
        if not ev:
            return jsonify({"error": "Event not found"}), 404
        rows = conn.execute("""
            SELECT id, minutes_before, sent_at, created_at
            FROM event_reminders WHERE event_id = ? AND user_id = ?
            ORDER BY minutes_before
        """, (event_id, g.user_id)).fetchall()
    return jsonify({"event_id": event_id, "reminders": [dict(r) for r in rows]})


@rm_bp.route("/<room>/events/<event_id>/reminders", methods=["POST"])
@require_auth
@rate_limit(max_calls=20, window_seconds=60)
def add_reminder(room, event_id):
    try:
        room = _validate_room(room)
        event_id = _validate_event_id(event_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    try:
        minutes = int(data.get("minutes_before", 15))
    except (TypeError, ValueError):
        return jsonify({"error": "minutes_before must be an integer"}), 400
    if minutes not in ALLOWED_MINUTES:
        return jsonify({"error": f"minutes_before must be one of {ALLOWED_MINUTES}"}), 400

    with get_db() as conn:
        ev = conn.execute(
            "SELECT starts_at FROM room_events WHERE id = ? AND room_id = ?",
            (event_id, room),
        ).fetchone()
        if not ev:
            return jsonify({"error": "Event not found"}), 404
        try:
            conn.execute(
                "INSERT INTO event_reminders (event_id, user_id, minutes_before) "
                "VALUES (?, ?, ?)", (event_id, g.user_id, minutes),
            )
        except Exception:
            return jsonify({"error": "Reminder already exists"}), 409

    return jsonify({"event_id": event_id, "minutes_before": minutes}), 201


@rm_bp.route("/<room>/events/<event_id>/reminders/<int:minutes>", methods=["DELETE"])
@require_auth
def delete_reminder(room, event_id, minutes):
    try:
        room = _validate_room(room)
        event_id = _validate_event_id(event_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM event_reminders "
            "WHERE event_id = ? AND user_id = ? AND minutes_before = ?",
            (event_id, g.user_id, minutes),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": minutes})


# ---------------------------------------------------------------------
# Background tick (called from workspace.scheduler)
# ---------------------------------------------------------------------
def tick(now=None) -> int:
    """Dispatch due reminders. Returns count delivered."""
    if now is None:
        now = datetime.now(timezone.utc)
    dispatched = 0

    with get_db() as conn:
        rows = conn.execute("""
            SELECT r.id, r.event_id, r.user_id, r.minutes_before,
                   e.title, e.starts_at, e.room_id
            FROM event_reminders r
            JOIN room_events e ON e.id = r.event_id
            WHERE r.sent_at IS NULL
        """).fetchall()

        for r in rows:
            try:
                starts_at = parse_iso(
                    (r["starts_at"] or "").replace("Z", "+00:00"))
                if starts_at.tzinfo is None:
                    starts_at = starts_at.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            trigger_at = starts_at - timedelta(minutes=r["minutes_before"])
            if trigger_at <= now:
                # Dispatch
                try:
                    from .notifications import send_push
                    send_push(
                        r["user_id"],
                        f"Upcoming: {r['title']}",
                        f"Starts in {r['minutes_before']} minutes in {r['room_id']}",
                        {"kind": "event_reminder", "event_id": r["event_id"]},
                    )
                except Exception:
                    pass
                conn.execute(
                    "UPDATE event_reminders SET sent_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (r["id"],),
                )
                dispatched += 1

    return dispatched
