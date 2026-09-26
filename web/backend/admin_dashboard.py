"""Admin dashboard API (Phase 16).

All endpoints require an authenticated user whose id matches ADMIN_USER_ID
(default: 1 — the first registered user). Read-only except for the
destructive DELETE /api/admin/audit endpoint.
"""
import json
import os
import platform
import sys
from functools import wraps

from flask import Blueprint, request, jsonify, g

from .auth import require_auth
from .database import get_db, get_db_path, _USE_PG
from .middleware import METRICS

admin_dash_bp = Blueprint("admin_dash", __name__, url_prefix="/api/admin")


def _admin_user_id() -> int:
    try:
        return int(os.environ.get("ADMIN_USER_ID", "1"))
    except ValueError:
        return 1


def require_admin(f):
    """Verify JWT first (via require_auth), then check admin user id."""
    @require_auth
    @wraps(f)
    def wrapper(*args, **kwargs):
        if g.user_id != _admin_user_id():
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return wrapper


def _limit(default=100, maximum=500):
    try:
        return min(int(request.args.get("limit", default)), maximum)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------
@admin_dash_bp.route("/stats", methods=["GET"])
@require_admin
def stats():
    with get_db() as conn:
        users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        rooms = conn.execute("SELECT COUNT(*) AS n FROM rooms").fetchone()["n"]
        members = conn.execute("SELECT COUNT(*) AS n FROM room_members").fetchone()["n"]
        messages = conn.execute("SELECT COUNT(*) AS n FROM chat_messages").fetchone()["n"]
        calcs = conn.execute("SELECT COUNT(*) AS n FROM calculations").fetchone()["n"]
        files = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes), 0) AS bytes FROM room_files"
        ).fetchone()
        audit = conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
        invites = conn.execute("SELECT COUNT(*) AS n FROM room_invites").fetchone()["n"]

    return jsonify({
        "users": users,
        "rooms": rooms,
        "room_members": members,
        "invites": invites,
        "chat_messages": messages,
        "calculations": calcs,
        "files": {"count": files["n"], "total_bytes": files["bytes"]},
        "audit_entries": audit,
    })


# ---------------------------------------------------------------------
# Server info
# ---------------------------------------------------------------------
@admin_dash_bp.route("/server-info", methods=["GET"])
@require_admin
def server_info():
    return jsonify({
        "version": "0.16.0",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "db_backend": "postgres" if _USE_PG else "sqlite",
        "db_path": "(postgres)" if _USE_PG else get_db_path(),
        "uptime_seconds": round(METRICS.uptime_seconds(), 2),
        "admin_user_id": _admin_user_id(),
    })


# ---------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------
@admin_dash_bp.route("/users", methods=["GET"])
@require_admin
def users():
    limit = _limit(100, 500)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT u.id, u.username, u.email, u.created_at, "
            "  (SELECT COUNT(*) FROM room_members WHERE user_id = u.id) AS room_count, "
            "  (SELECT COUNT(*) FROM calculations WHERE user_id = u.id) AS calc_count "
            "FROM users u ORDER BY u.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return jsonify({"users": [dict(r) for r in rows], "count": len(rows)})


# ---------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------
@admin_dash_bp.route("/rooms", methods=["GET"])
@require_admin
def rooms():
    limit = _limit(100, 500)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT r.name, r.created_at, u.username AS owner, "
            "  (SELECT COUNT(*) FROM room_members WHERE room_name = r.name) AS member_count, "
            "  (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.name) AS message_count, "
            "  (SELECT COUNT(*) FROM room_files WHERE room_id = r.name) AS file_count "
            "FROM rooms r JOIN users u ON u.id = r.owner_id "
            "ORDER BY r.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        # Also list open (unclaimed) rooms referenced by chat/files
        open_rows = conn.execute(
            "SELECT DISTINCT room_id FROM chat_messages "
            "WHERE room_id NOT IN (SELECT name FROM rooms)"
        ).fetchall()
    return jsonify({
        "rooms": [dict(r) for r in rows],
        "unclaimed_rooms": [r["room_id"] for r in open_rows],
        "count": len(rows),
    })


# ---------------------------------------------------------------------
# Audit log viewer
# ---------------------------------------------------------------------
@admin_dash_bp.route("/audit", methods=["GET"])
@require_admin
def audit_list():
    limit = _limit(200, 1000)
    where, params = [], []

    actor = request.args.get("actor")
    action = request.args.get("action")
    status = request.args.get("status")
    if actor:
        where.append("(actor_id = ? OR resource_id = ?)")
        params.extend([actor, actor])
    if action:
        where.append("action = ?")
        params.append(action)
    if status:
        where.append("status = ?")
        params.append(status)

    sql = "SELECT * FROM audit_log"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        distinct_actions = [
            r["action"] for r in conn.execute(
                "SELECT DISTINCT action FROM audit_log ORDER BY action"
            ).fetchall()
        ]

    out = []
    for r in rows:
        d = dict(r)
        if d.get("details"):
            try:
                d["details"] = json.loads(d["details"])
            except (TypeError, json.JSONDecodeError):
                pass
        out.append(d)

    return jsonify({
        "entries": out,
        "actions": distinct_actions,
        "count": len(out),
    })


# ---------------------------------------------------------------------
# Metrics (JSON)
# ---------------------------------------------------------------------
@admin_dash_bp.route("/metrics", methods=["GET"])
@require_admin
def metrics_json():
    return jsonify({
        "uptime_seconds": round(METRICS.uptime_seconds(), 2),
        "requests_total": [
            {"method": k[0], "path": k[1], "status": k[2], "count": v}
            for k, v in sorted(METRICS.requests_total.items())
        ],
        "errors_total": dict(METRICS.errors_total),
    })


# ---------------------------------------------------------------------
# Danger zone — clear audit log
# ---------------------------------------------------------------------
@admin_dash_bp.route("/audit", methods=["DELETE"])
@require_admin
def clear_audit():
    with get_db() as conn:
        cur = conn.execute("DELETE FROM audit_log")
        n = cur.rowcount
    return jsonify({"deleted_count": n})

# ---------------------------------------------------------------------
# Retention jobs (Phase 24)
# ---------------------------------------------------------------------
@admin_dash_bp.route("/retention", methods=["GET"])
@require_admin
def retention_status():
    from .jobs import snapshot
    return jsonify(snapshot())


@admin_dash_bp.route("/retention/run", methods=["POST"])
@require_admin
def retention_run_now():
    from .jobs import run_retention
    deleted = run_retention()
    return jsonify({"deleted": deleted})

