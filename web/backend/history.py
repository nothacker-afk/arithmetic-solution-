"""Calculation history blueprint (JWT-protected)."""
from flask import Blueprint, request, jsonify, g

from .auth import require_auth
from .database import get_db


history_bp = Blueprint("history", __name__, url_prefix="/api/history")


@history_bp.route("", methods=["POST"])
@require_auth
def save():
    data = request.get_json(silent=True) or {}
    expression = (data.get("expression") or "").strip()
    result = str(data.get("result", "")).strip()
    operation = data.get("operation")

    if not expression or not result:
        return jsonify({"error": "expression and result required"}), 400

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO calculations (user_id, expression, result, operation) "
            "VALUES (?, ?, ?, ?)",
            (g.user_id, expression, result, operation),
        )
        calc_id = cur.lastrowid

    return jsonify({
        "id": calc_id,
        "expression": expression,
        "result": result,
        "operation": operation,
    }), 201


@history_bp.route("", methods=["GET"])
@require_auth
def list_history():
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except ValueError:
        limit = 50

    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, expression, result, operation, created_at "
            "FROM calculations WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (g.user_id, limit),
        ).fetchall()

    return jsonify([dict(r) for r in rows])


@history_bp.route("/<int:calc_id>", methods=["DELETE"])
@require_auth
def delete(calc_id):
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM calculations WHERE id = ? AND user_id = ?",
            (calc_id, g.user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": calc_id})


@history_bp.route("", methods=["DELETE"])
@require_auth
def clear():
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM calculations WHERE user_id = ?", (g.user_id,)
        )
        n = cur.rowcount
    return jsonify({"deleted_count": n})
