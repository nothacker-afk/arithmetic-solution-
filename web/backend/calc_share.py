"""Shareable calculation links (Phase 88).

Anyone can view a shared calculation. Saving requires auth.

Endpoints:
    POST   /api/calc/save              {expression, result, steps?, is_public?}
    GET    /api/calc/saved             list mine
    GET    /api/calc/saved/<id>        view (increments views)
    DELETE /api/calc/saved/<id>        delete mine
"""
from __future__ import annotations
import json
import uuid

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

share_bp = Blueprint("calc_share", __name__, url_prefix="/api/calc")

SHARE_ID_RE = __import__("re").compile(r"^[0-9a-f]{16}$")


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


@share_bp.route("/save", methods=["POST"])
@require_auth
@rate_limit(max_calls=60, window_seconds=60)
def save_calc():
    data = request.get_json(silent=True) or {}
    expr = (data.get("expression") or "").strip()
    result = str(data.get("result") or "").strip()
    is_public = 1 if data.get("is_public") else 0
    steps = data.get("steps") or []

    if not expr or not result:
        return jsonify({"error": "expression and result required"}), 400
    if len(expr) > 1000:
        return jsonify({"error": "expression too long"}), 400

    # Validate steps is JSON-serializable
    try:
        steps_json = json.dumps(steps)
        if len(steps_json) > 20000:
            return jsonify({"error": "steps too large"}), 400
    except Exception:
        return jsonify({"error": "invalid steps"}), 400

    calc_id = _new_id()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO saved_calculations
            (id, user_id, expression, result, steps, is_public)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (calc_id, g.user_id, expr, result, steps_json, is_public))

    return jsonify({
        "id": calc_id,
        "expression": expr,
        "result": result,
        "is_public": bool(is_public),
        "url": f"/calc/{calc_id}",
    }), 201


@share_bp.route("/saved", methods=["GET"])
@require_auth
def list_saved():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, expression, result, is_public, views, created_at
            FROM saved_calculations
            WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 100
        """, (g.user_id,)).fetchall()
    return jsonify({"calculations": [dict(r) for r in rows]})


@share_bp.route("/saved/<calc_id>", methods=["GET"])
def view_saved(calc_id):
    if not SHARE_ID_RE.match(calc_id or ""):
        return jsonify({"error": "Invalid id"}), 400

    with get_db() as conn:
        row = conn.execute("""
            SELECT id, expression, result, steps, is_public, views, created_at
            FROM saved_calculations WHERE id = ?
        """, (calc_id,)).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404

        # Public calcs are visible to anyone; private ones only to owner.
        viewer_id = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                import jwt as _jwt
                from .config import Config
                payload = _jwt.decode(auth[7:].strip(), Config.JWT_SECRET,
                                      algorithms=[Config.JWT_ALGORITHM])
                viewer_id = int(payload["sub"])
            except Exception:
                pass

        if not row["is_public"] and viewer_id != row_user_id(conn, calc_id):
            return jsonify({"error": "Not found"}), 404

        # Increment views
        conn.execute("UPDATE saved_calculations SET views = views + 1 WHERE id = ?",
                     (calc_id,))

    out = dict(row)
    try:
        out["steps"] = json.loads(out["steps"] or "[]")
    except Exception:
        out["steps"] = []
    out["is_public"] = bool(out["is_public"])
    return jsonify(out)


def row_user_id(conn, calc_id):
    r = conn.execute("SELECT user_id FROM saved_calculations WHERE id = ?",
                     (calc_id,)).fetchone()
    return r["user_id"] if r else None


@share_bp.route("/saved/<calc_id>", methods=["DELETE"])
@require_auth
def delete_saved(calc_id):
    if not SHARE_ID_RE.match(calc_id or ""):
        return jsonify({"error": "Invalid id"}), 400
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM saved_calculations WHERE id = ? AND user_id = ?",
            (calc_id, g.user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": calc_id})
