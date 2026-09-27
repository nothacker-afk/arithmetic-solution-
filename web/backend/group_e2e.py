"""Group E2E encryption helpers (Phase 70).

Group messages are already encrypted at rest. What's missing is a
*stable, shareable* key derivation salt per group, so any member with
the passphrase derives the same AES key regardless of device.

Endpoints:
    GET    /api/groups/<id>/encryption        returns salt + key_version (public to members)
    POST   /api/groups/<id>/encryption/rotate rotate salt + bump key_version (owner only)
"""
import secrets

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

grp_e2e_bp = Blueprint("group_e2e", __name__, url_prefix="/api/groups")


def _is_member(conn, group_id, user_id):
    return conn.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    ).fetchone() is not None


def _ensure_salt(conn, group_id, user_id):
    row = conn.execute(
        "SELECT salt, key_version FROM group_keys WHERE group_id = ?", (group_id,),
    ).fetchone()
    if row:
        return row
    salt = secrets.token_hex(16)
    conn.execute("""
        INSERT INTO group_keys (group_id, salt, key_version, created_by)
        VALUES (?, ?, 1, ?)
    """, (group_id, salt, user_id))
    return {"salt": salt, "key_version": 1}


@grp_e2e_bp.route("/<int:group_id>/encryption", methods=["GET"])
@require_auth
def get_encryption(group_id):
    with get_db() as conn:
        if not _is_member(conn, group_id, g.user_id):
            return jsonify({"error": "Not a member"}), 403
        row = _ensure_salt(conn, group_id, g.user_id)

    return jsonify({
        "group_id": group_id,
        "salt": row["salt"],
        "key_version": row["key_version"],
        "hint": "Derive key = PBKDF2(passphrase, 'group:' + group_id + ':' + salt, 100k, SHA256)",
    })


@grp_e2e_bp.route("/<int:group_id>/encryption/rotate", methods=["POST"])
@require_auth
@rate_limit(max_calls=5, window_seconds=300)
def rotate(group_id):
    with get_db() as conn:
        me = conn.execute(
            "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, g.user_id),
        ).fetchone()
        if not me or me["role"] != "owner":
            return jsonify({"error": "Only the group owner can rotate keys"}), 403

        new_salt = secrets.token_hex(16)
        row = conn.execute(
            "SELECT key_version FROM group_keys WHERE group_id = ?", (group_id,),
        ).fetchone()
        new_version = (row["key_version"] + 1) if row else 1

        conn.execute("""
            INSERT INTO group_keys (group_id, salt, key_version, created_by, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(group_id) DO UPDATE SET
                salt = excluded.salt,
                key_version = excluded.key_version,
                updated_at = CURRENT_TIMESTAMP
        """, (group_id, new_salt, new_version, g.user_id))

    log_event("group.rotate_key", actor_id=g.user_id, resource="group",
              resource_id=str(group_id), details={"new_version": new_version})

    return jsonify({
        "group_id": group_id,
        "salt": new_salt,
        "key_version": new_version,
        "notice": "Old encrypted messages will not decrypt with the new key.",
    }), 200
