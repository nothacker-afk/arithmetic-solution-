"""Admin analytics (Phase 60).

Time-series and aggregate metrics for the admin dashboard.

Endpoints:
    GET /api/admin/analytics?days=30
    GET /api/admin/analytics/users?days=30
    GET /api/admin/analytics/rooms?limit=10
"""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify

from .database import get_db
from .admin_dashboard import require_admin

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/admin/analytics")


def _series(conn, table, timestamp_col, days):
    start = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()
    rows = conn.execute(f"""
        SELECT DATE({timestamp_col}) AS day, COUNT(*) AS n
        FROM {table}
        WHERE DATE({timestamp_col}) >= ?
        GROUP BY DATE({timestamp_col})
    """, (start.isoformat(),)).fetchall()
    counts = {r["day"]: r["n"] for r in rows}
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        out.append({"day": d, "count": counts.get(d, 0)})
    return out


@analytics_bp.route("", methods=["GET"])
@require_admin
def overview():
    try:
        days = min(int(request.args.get("days", 30)), 365)
    except ValueError:
        days = 30

    with get_db() as conn:
        messages = _series(conn, "chat_messages", "created_at", days)
        users = _series(conn, "users", "created_at", days)
        calcs = _series(conn, "calculations", "created_at", days)
        dm_messages = _series(conn, "dm_messages", "created_at", days)
        audit = _series(conn, "audit_log", "created_at", days)

        total_users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        total_rooms = conn.execute("SELECT COUNT(*) AS n FROM rooms").fetchone()["n"]
        total_msgs = conn.execute("SELECT COUNT(*) AS n FROM chat_messages").fetchone()["n"]
        total_dms = conn.execute("SELECT COUNT(*) AS n FROM dm_messages").fetchone()["n"]

    return jsonify({
        "days": days,
        "totals": {
            "users": total_users,
            "rooms": total_rooms,
            "chat_messages": total_msgs,
            "dm_messages": total_dms,
        },
        "series": {
            "users": users,
            "messages": messages,
            "calculations": calcs,
            "dms": dm_messages,
            "audit": audit,
        },
    })


@analytics_bp.route("/users", methods=["GET"])
@require_admin
def active_users():
    try:
        days = min(int(request.args.get("days", 30)), 365)
    except ValueError:
        days = 30
    limit = 10

    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_db() as conn:
        rows = conn.execute("""
            SELECT username, COUNT(*) AS n
            FROM chat_messages
            WHERE created_at >= ?
            GROUP BY username
            ORDER BY n DESC LIMIT ?
        """, (start, limit)).fetchall()

    return jsonify({"days": days, "top_users": [dict(r) for r in rows]})


@analytics_bp.route("/rooms", methods=["GET"])
@require_admin
def busiest_rooms():
    try:
        limit = min(int(request.args.get("limit", 10)), 50)
    except ValueError:
        limit = 10
    with get_db() as conn:
        rows = conn.execute("""
            SELECT room_id, COUNT(*) AS n
            FROM chat_messages
            GROUP BY room_id
            ORDER BY n DESC LIMIT ?
        """, (limit,)).fetchall()
    return jsonify({"top_rooms": [dict(r) for r in rows]})
