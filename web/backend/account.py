"""Account data ownership endpoints (Phase 17).

Provides:
    GET    /api/account/data-summary     — what we hold, in aggregate
    GET    /api/account/export           — full download (json or zip)
    DELETE /api/account                  — irreversible, cascades cleanly
    GET    /api/account/backups          — list user's encrypted backups
    POST   /api/account/backups          — store a new encrypted backup
    GET    /api/account/backups/<id>     — download backup blob
    DELETE /api/account/backups/<id>     — delete a backup
"""
import base64
import io
import json
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, request, jsonify, g, send_file, Response
from werkzeug.security import check_password_hash

from .config import Config
from .database import get_db
from .auth import require_auth
from .audit import log_event
from .rate_limit import rate_limit

account_bp = Blueprint("account", __name__, url_prefix="/api/account")

BACKUP_ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_BACKUP_BYTES = int(os.environ.get("MAX_BACKUP_BYTES", str(20 * 1024 * 1024)))


def _backup_dir() -> Path:
    base = Path(Config.FILE_STORAGE_DIR).parent / "arithmetic_backups"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"


def _collect_user_data(user_id: int) -> dict:
    """Assemble everything we know about a user."""
    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            raise LookupError("User not found")

        calcs = conn.execute(
            "SELECT id, expression, result, operation, created_at "
            "FROM calculations WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()

        rooms = conn.execute(
            "SELECT r.name, m.role, m.joined_at "
            "FROM rooms r JOIN room_members m ON m.room_name = r.name "
            "WHERE m.user_id = ? ORDER BY m.joined_at",
            (user_id,),
        ).fetchall()

        prefs = conn.execute(
            "SELECT theme, language, updated_at FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        audit = conn.execute(
            "SELECT action, resource, resource_id, status, created_at "
            "FROM audit_log WHERE actor_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()

        uploaded_files = conn.execute(
            "SELECT id, room_id, filename, size_bytes, created_at "
            "FROM room_files WHERE uploaded_by = ? ORDER BY created_at",
            (user["username"],),
        ).fetchall()

    return {
        "exported_at": _now_iso(),
        "schema_version": "1",
        "user": dict(user),
        "preferences": dict(prefs) if prefs else None,
        "calculations": [dict(r) for r in calcs],
        "rooms": [dict(r) for r in rooms],
        "uploaded_files": [dict(r) for r in uploaded_files],
        "audit_trail": [dict(r) for r in audit],
    }


# ---------------------------------------------------------------------
# Data summary
# ---------------------------------------------------------------------
@account_bp.route("/data-summary", methods=["GET"])
@require_auth
def data_summary():
    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username, email, created_at FROM users WHERE id = ?",
            (g.user_id,),
        ).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        calc_count = conn.execute(
            "SELECT COUNT(*) AS n FROM calculations WHERE user_id = ?", (g.user_id,),
        ).fetchone()["n"]

        room_count = conn.execute(
            "SELECT COUNT(*) AS n FROM room_members WHERE user_id = ?", (g.user_id,),
        ).fetchone()["n"]

        owned_rooms = conn.execute(
            "SELECT COUNT(*) AS n FROM rooms WHERE owner_id = ?", (g.user_id,),
        ).fetchone()["n"]

        file_count = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes), 0) AS bytes "
            "FROM room_files WHERE uploaded_by = ?",
            (user["username"],),
        ).fetchone()

        backup_count = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes), 0) AS bytes "
            "FROM account_backups WHERE user_id = ?",
            (g.user_id,),
        ).fetchone()

        audit_count = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_log WHERE actor_id = ?", (g.user_id,),
        ).fetchone()["n"]

    return jsonify({
        "user": dict(user),
        "calculations": calc_count,
        "rooms_joined": room_count,
        "rooms_owned": owned_rooms,
        "uploaded_files": {"count": file_count["n"], "total_bytes": file_count["bytes"]},
        "backups": {"count": backup_count["n"], "total_bytes": backup_count["bytes"]},
        "audit_entries": audit_count,
        "retention_policy": {
            "calculations": "deleted with account",
            "chat_messages": "anonymized to '[deleted]'",
            "uploaded_files": "marked uploaded_by='[deleted]'",
            "audit_log": "actor_id, ip, user_agent cleared",
            "owned_rooms": "transferred to oldest member, or deleted if none",
        },
    })


# ---------------------------------------------------------------------
# Full export
# ---------------------------------------------------------------------
@account_bp.route("/export", methods=["GET"])
@require_auth
@rate_limit(max_calls=5, window_seconds=60)
def export():
    fmt = (request.args.get("format") or "json").lower()
    if fmt not in ("json", "zip"):
        return jsonify({"error": "format must be 'json' or 'zip'"}), 400

    try:
        data = _collect_user_data(g.user_id)
    except LookupError:
        return jsonify({"error": "User not found"}), 404

    log_event("account.export", actor_id=g.user_id, resource="user",
              resource_id=str(g.user_id), details={"format": fmt})

    payload = json.dumps(data, indent=2, default=str).encode("utf-8")

    if fmt == "json":
        resp = Response(payload, mimetype="application/json")
        resp.headers["Content-Disposition"] = (
            f'attachment; filename="account-{g.user_id}-export.json"'
        )
        return resp

    # ZIP: JSON + raw uploaded file blobs (encrypted at rest)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("account.json", payload)

        upload_dir = Path(Config.FILE_STORAGE_DIR)
        for f in data["uploaded_files"]:
            path = upload_dir / f["room_id"] / f"{f['id']}.bin"
            if path.exists():
                zf.write(path, arcname=f"files/{f['room_id']}/{f['id']}.bin")

        zf.writestr(
            "README.txt",
            "Files under files/ are the encrypted blobs as stored on the server.\n"
            "To read them, use the room passphrase in the web app's Live tab.\n",
        )

    buf.seek(0)
    resp = Response(buf.getvalue(), mimetype="application/zip")
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="account-{g.user_id}-export.zip"'
    )
    return resp


# ---------------------------------------------------------------------
# Account deletion
# ---------------------------------------------------------------------
@account_bp.route("", methods=["DELETE"])
@require_auth
@rate_limit(max_calls=3, window_seconds=300)
def delete_account():
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    confirm = (data.get("confirm") or "").strip()

    if confirm != "DELETE":
        return jsonify({"error": "Set confirm='DELETE' to proceed"}), 400

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE id = ?",
            (g.user_id,),
        ).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
        if not check_password_hash(user["password_hash"], password):
            log_event("account.delete", actor_id=g.user_id, resource="user",
                      resource_id=str(g.user_id), status="failed",
                      details={"reason": "bad_password"})
            return jsonify({"error": "Invalid password"}), 401

        username = user["username"]

        # ---- 1. Transfer or delete owned rooms ----
        owned = conn.execute(
            "SELECT name FROM rooms WHERE owner_id = ?", (g.user_id,),
        ).fetchall()
        for room in owned:
            other = conn.execute(
                "SELECT user_id FROM room_members "
                "WHERE room_name = ? AND user_id != ? "
                "ORDER BY joined_at LIMIT 1",
                (room["name"], g.user_id),
            ).fetchone()
            if other:
                # Transfer ownership
                conn.execute("UPDATE rooms SET owner_id = ? WHERE name = ?",
                             (other["user_id"], room["name"]))
                conn.execute(
                    "UPDATE room_members SET role = 'owner' "
                    "WHERE room_name = ? AND user_id = ?",
                    (room["name"], other["user_id"]),
                )
            else:
                # No other members — delete the room and everything in it
                conn.execute("DELETE FROM rooms WHERE name = ?", (room["name"],))
                conn.execute("DELETE FROM room_members WHERE room_name = ?", (room["name"],))
                conn.execute("DELETE FROM room_invites WHERE room_name = ?", (room["name"],))
                conn.execute("DELETE FROM chat_messages WHERE room_id = ?", (room["name"],))
                conn.execute("DELETE FROM room_files WHERE room_id = ?", (room["name"],))

        # ---- 2. Anonymize shared content ----
        conn.execute(
            "UPDATE chat_messages SET username = '[deleted]' WHERE username = ?",
            (username,),
        )
        conn.execute(
            "UPDATE room_files SET uploaded_by = '[deleted]' WHERE uploaded_by = ?",
            (username,),
        )

        # ---- 3. Delete personal rows ----
        conn.execute("DELETE FROM room_invites WHERE created_by = ?", (g.user_id,))
        conn.execute("DELETE FROM account_backups WHERE user_id = ?", (g.user_id,))

        # ---- 4. Anonymize audit trail (keep for compliance) ----
        conn.execute(
            "UPDATE audit_log SET actor_id = NULL, ip = NULL, user_agent = NULL "
            "WHERE actor_id = ?",
            (g.user_id,),
        )

        # ---- 5. Delete user (CASCADE removes calculations, memberships, prefs) ----
        conn.execute("DELETE FROM users WHERE id = ?", (g.user_id,))

    # Remove backup blobs from disk
    for blob in _backup_dir().glob(f"*{g.user_id}*"):
        try:
            blob.unlink()
        except OSError:
            pass

    # Log the deletion (actor_id is gone; leave NULL)
    log_event("account.delete", actor_id=None, resource="user",
              resource_id=str(g.user_id), status="ok",
              details={"username": username})

    return jsonify({"deleted": True, "username": username})


# ---------------------------------------------------------------------
# Encrypted backups
# ---------------------------------------------------------------------
@account_bp.route("/backups", methods=["GET"])
@require_auth
def list_backups():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, label, size_bytes, created_at "
            "FROM account_backups WHERE user_id = ? ORDER BY created_at DESC",
            (g.user_id,),
        ).fetchall()
    return jsonify({"backups": [dict(r) for r in rows]})


@account_bp.route("/backups", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=300)
def create_backup():
    data = request.get_json(silent=True) or {}
    label = (data.get("label") or "").strip()[:64] or None
    ciphertext_b64 = data.get("ciphertext_b64")

    if not isinstance(ciphertext_b64, str) or not ciphertext_b64:
        return jsonify({"error": "ciphertext_b64 is required"}), 400

    try:
        blob = base64.b64decode(ciphertext_b64, validate=True)
    except Exception:
        return jsonify({"error": "ciphertext_b64 is not valid base64"}), 400

    if len(blob) > MAX_BACKUP_BYTES:
        return jsonify({"error": f"Backup exceeds {MAX_BACKUP_BYTES} byte limit"}), 413

    backup_id = uuid.uuid4().hex
    path = _backup_dir() / f"{backup_id}-{g.user_id}.bin"
    path.write_bytes(blob)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO account_backups (id, user_id, label, size_bytes) "
            "VALUES (?, ?, ?, ?)",
            (backup_id, g.user_id, label, len(blob)),
        )

    log_event("account.backup.create", actor_id=g.user_id, resource="backup",
              resource_id=backup_id, details={"size_bytes": len(blob), "label": label})

    return jsonify({
        "id": backup_id,
        "label": label,
        "size_bytes": len(blob),
    }), 201


@account_bp.route("/backups/<backup_id>", methods=["GET"])
@require_auth
def download_backup(backup_id):
    if not BACKUP_ID_RE.match(backup_id):
        return jsonify({"error": "Invalid backup id"}), 400

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, label FROM account_backups WHERE id = ? AND user_id = ?",
            (backup_id, g.user_id),
        ).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404

    path = _backup_dir() / f"{backup_id}-{g.user_id}.bin"
    if not path.exists():
        return jsonify({"error": "Backup blob missing on disk"}), 410

    return send_file(
        str(path),
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=f"backup-{backup_id}.enc",
    )


@account_bp.route("/backups/<backup_id>", methods=["DELETE"])
@require_auth
def delete_backup(backup_id):
    if not BACKUP_ID_RE.match(backup_id):
        return jsonify({"error": "Invalid backup id"}), 400

    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM account_backups WHERE id = ? AND user_id = ?",
            (backup_id, g.user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not found"}), 404

    try:
        (_backup_dir() / f"{backup_id}-{g.user_id}.bin").unlink()
    except FileNotFoundError:
        pass

    log_event("account.backup.delete", actor_id=g.user_id, resource="backup",
              resource_id=backup_id)

    return jsonify({"deleted": backup_id})
