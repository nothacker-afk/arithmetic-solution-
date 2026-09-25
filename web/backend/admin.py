"""Audit query endpoint (Phase 13).

Non-admin users see only their own audit rows. Admins (user_id == 1 by
default, or set ADMIN_USER_ID) see all rows.
"""
import json
import os

from flask import Blueprint, request, jsonify, g

from .auth import require_auth
from .database import get_db

admin_bp = Blueprint("admin", __name__, url_prefix="/api/audit")


def _admin_user_id() -> int:
    try:
        return int(os.environ.get("ADMIN_USER_ID", "1"))
    except ValueError:
        return 1


@admin_bp.route("", methods=["GET"])
@require_auth
def list_audit():
    try:
        limit = min(int(request.args.get("limit", 100)), 500)
    except ValueError:
        limit = 100

    action_filter = request.args.get("action")
    is_admin = g.user_id == _admin_user_id()

    where = []
    params = []
    if not is_admin:
        where.append("actor_id = ?")
        params.append(g.user_id)
    if action_filter:
        where.append("action = ?")
        params.append(action_filter)

    sql = "SELECT * FROM audit_log"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

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
        "is_admin": is_admin,
        "count": len(out),
        "entries": out,
    })
