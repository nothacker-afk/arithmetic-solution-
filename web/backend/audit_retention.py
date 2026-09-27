"""Per-action audit retention policies (Phase 72).

Owners (via admin) can configure per-action retention overrides.
Falls back to the global RETENTION_AUDIT_DAYS when no policy matches.

Endpoints:
    GET    /api/admin/audit_retention              list policies
    POST   /api/admin/audit_retention              {action_pattern, retention_days}
    DELETE /api/admin/audit_retention/<id>         remove policy
    GET    /api/admin/audit_retention/preview      how many rows each policy would delete now
"""
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .audit import log_event

ar_bp = Blueprint("audit_retention", __name__, url_prefix="/api/admin/audit_retention")

# We reuse the existing admin guard
from .admin_dashboard import require_admin  # noqa: E402

# action patterns: "auth.*", "room.*", or exact "auth.login"
PATTERN_RE = re.compile(r"^[a-zA-Z0-9_.*]{2,64}$")


def _validate_pattern(pattern: str) -> str:
    if not PATTERN_RE.match(pattern or ""):
        raise ValueError("pattern must be 2-64 chars: letters, digits, '.', '*'")
    if pattern.count("*") > 1:
        raise ValueError("only one '*' allowed")
    if "*" in pattern and not pattern.endswith("*"):
        raise ValueError("'*' must be at the end")
    return pattern


def _apply_policies_to_sql(policies):
    """Build a SELECT for the preview endpoint."""
    return policies


@ar_bp.route("", methods=["GET"])
@require_admin
def list_policies():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, action_pattern, retention_days, updated_at
            FROM audit_retention_policies
            ORDER BY action_pattern
        """).fetchall()
    return jsonify({"policies": [dict(r) for r in rows], "count": len(rows)})


@ar_bp.route("", methods=["POST"])
@require_admin
def create_policy():
    data = request.get_json(silent=True) or {}
    pattern = (data.get("action_pattern") or "").strip()
    try:
        pattern = _validate_pattern(pattern)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        days = int(data.get("retention_days", 365))
    except (TypeError, ValueError):
        return jsonify({"error": "retention_days must be an integer"}), 400
    if days < 1 or days > 3650:
        return jsonify({"error": "retention_days must be 1..3650"}), 400

    with get_db() as conn:
        conn.execute("""
            INSERT INTO audit_retention_policies
            (action_pattern, retention_days, created_by, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(action_pattern) DO UPDATE SET
                retention_days = excluded.retention_days,
                updated_at = CURRENT_TIMESTAMP
        """, (pattern, days, g.user_id))

    log_event("audit_retention.set", actor_id=g.user_id, resource="policy",
              resource_id=pattern, details={"days": days})
    return jsonify({"action_pattern": pattern, "retention_days": days}), 201


@ar_bp.route("/<int:policy_id>", methods=["DELETE"])
@require_admin
def delete_policy(policy_id):
    with get_db() as conn:
        cur = conn.execute("DELETE FROM audit_retention_policies WHERE id = ?", (policy_id,))
        if cur.rowcount == 0:
            return jsonify({"error": "Not found"}), 404
    log_event("audit_retention.delete", actor_id=g.user_id, resource="policy",
              resource_id=str(policy_id))
    return jsonify({"deleted": policy_id})


@ar_bp.route("/preview", methods=["GET"])
@require_admin
def preview():
    """For each policy, count rows that would be deleted on next retention run."""
    with get_db() as conn:
        policies = conn.execute(
            "SELECT action_pattern, retention_days FROM audit_retention_policies"
        ).fetchall()
        out = []
        for p in policies:
            pattern = p["action_pattern"]
            days = p["retention_days"]
            like = pattern.replace("*", "%") if pattern.endswith("*") else pattern
            if pattern.endswith("*"):
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM audit_log "
                    "WHERE action LIKE ? "
                    "  AND created_at < datetime('now', '-' || ? || ' days')",
                    (like, days),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM audit_log "
                    "WHERE action = ? "
                    "  AND created_at < datetime('now', '-' || ? || ' days')",
                    (pattern, days),
                ).fetchone()
            out.append({
                "action_pattern": pattern,
                "retention_days": days,
                "would_delete": row["n"],
            })

    return jsonify({"previews": out})


# ---------------------------------------------------------------------
# Called by jobs.run_retention()
# ---------------------------------------------------------------------
def apply_per_action_retention(conn) -> dict:
    """Delete audit rows per policy. Returns {pattern: count}."""
    deleted = {}
    policies = conn.execute(
        "SELECT action_pattern, retention_days FROM audit_retention_policies"
    ).fetchall()
    for p in policies:
        pattern = p["action_pattern"]
        days = p["retention_days"]
        if pattern.endswith("*"):
            like = pattern.replace("*", "%")
            cur = conn.execute(
                "DELETE FROM audit_log WHERE action LIKE ? "
                "  AND created_at < datetime('now', '-' || ? || ' days')",
                (like, days),
            )
        else:
            cur = conn.execute(
                "DELETE FROM audit_log WHERE action = ? "
                "  AND created_at < datetime('now', '-' || ? || ' days')",
                (pattern, days),
            )
        if cur.rowcount:
            deleted[pattern] = cur.rowcount
    return deleted
