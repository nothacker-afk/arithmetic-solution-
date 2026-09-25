"""File sharing blueprint (Phase 10).

Files are stored as opaque blobs on disk. The server never decrypts them.
Metadata lives in SQLite. Client encrypts before upload and decrypts
after download using AES-GCM (see web/frontend/crypto.js).
"""
import base64
import os
import re
import uuid
from pathlib import Path

from flask import Blueprint, request, jsonify, send_file, abort

from .config import Config
from .database import get_db
from .rate_limit import rate_limit

files_bp = Blueprint("files", __name__, url_prefix="/api/files")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def _validate_room(room: str) -> str:
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


def _safe_filename(name: str) -> str:
    """Sanitize a filename: strip path separators, limit length."""
    name = (name or "").strip()
    name = Path(name).name  # drop any directory parts
    name = SAFE_NAME_RE.sub("_", name)
    if not name:
        name = "file.bin"
    return name[:128]


def _room_dir(room: str) -> Path:
    base = Path(Config.FILE_STORAGE_DIR)
    d = base / room
    d.mkdir(parents=True, exist_ok=True)
    return d


def _room_usage(room: str) -> tuple[int, int]:
    """Return (file_count, total_bytes) for a room."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes), 0) AS total "
            "FROM room_files WHERE room_id = ?",
            (room,),
        ).fetchone()
    return int(row["n"]), int(row["total"])


# ---------------------------------------------------------------------
# List files
# ---------------------------------------------------------------------
@files_bp.route("/<room>", methods=["GET"])
def list_files(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, filename, size_bytes, encrypted, uploaded_by, created_at "
            "FROM room_files WHERE room_id = ? "
            "ORDER BY created_at DESC LIMIT 200",
            (room,),
        ).fetchall()

    count, total = _room_usage(room)
    return jsonify({
        "room": room,
        "files": [dict(r) for r in rows],
        "usage": {"count": count, "total_bytes": total},
    })


# ---------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------
@files_bp.route("/<room>", methods=["POST"])
@rate_limit(max_calls=30, window_seconds=60)
def upload_file(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    filename = _safe_filename(data.get("filename", ""))
    ciphertext_b64 = data.get("ciphertext_b64")
    encrypted = bool(data.get("encrypted", True))
    uploaded_by = (data.get("uploaded_by") or "guest").strip()[:32] or "guest"

    if not isinstance(ciphertext_b64, str) or not ciphertext_b64:
        return jsonify({"error": "ciphertext_b64 is required"}), 400

    try:
        blob = base64.b64decode(ciphertext_b64, validate=True)
    except Exception:
        return jsonify({"error": "ciphertext_b64 is not valid base64"}), 400

    max_bytes = Config.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(blob) > max_bytes:
        return jsonify({
            "error": f"File exceeds {Config.MAX_FILE_SIZE_MB} MB limit"
        }), 413

    count, total = _room_usage(room)
    if count >= Config.MAX_FILES_PER_ROOM:
        return jsonify({"error": "Room file count limit reached"}), 413
    if total + len(blob) > Config.MAX_TOTAL_BYTES_PER_ROOM:
        return jsonify({"error": "Room storage quota exceeded"}), 413

    file_id = uuid.uuid4().hex
    room_dir = _room_dir(room)
    (room_dir / f"{file_id}.bin").write_bytes(blob)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO room_files "
            "(id, room_id, filename, size_bytes, encrypted, uploaded_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (file_id, room, filename, len(blob), 1 if encrypted else 0, uploaded_by),
        )

    return jsonify({
        "id": file_id,
        "filename": filename,
        "size_bytes": len(blob),
        "encrypted": encrypted,
        "uploaded_by": uploaded_by,
    }), 201


# ---------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------
@files_bp.route("/<room>/<file_id>", methods=["GET"])
def download_file(room, file_id):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # file_id must be a hex string
    if not re.fullmatch(r"[0-9a-f]{32}", file_id):
        return jsonify({"error": "Invalid file id"}), 400

    with get_db() as conn:
        row = conn.execute(
            "SELECT filename, encrypted FROM room_files "
            "WHERE id = ? AND room_id = ?",
            (file_id, room),
        ).fetchone()

    if not row:
        return jsonify({"error": "Not found"}), 404

    path = _room_dir(room) / f"{file_id}.bin"
    if not path.exists():
        return jsonify({"error": "File missing on disk"}), 410

    return send_file(
        str(path),
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=row["filename"] + ".enc" if row["encrypted"] else row["filename"],
    )


# ---------------------------------------------------------------------
# Delete one
# ---------------------------------------------------------------------
@files_bp.route("/<room>/<file_id>", methods=["DELETE"])
def delete_file(room, file_id):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not re.fullmatch(r"[0-9a-f]{32}", file_id):
        return jsonify({"error": "Invalid file id"}), 400

    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM room_files WHERE id = ? AND room_id = ?",
            (file_id, room),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not found"}), 404

    path = _room_dir(room) / f"{file_id}.bin"
    try:
        path.unlink()
    except FileNotFoundError:
        pass

    return jsonify({"deleted": file_id})


# ---------------------------------------------------------------------
# Clear room
# ---------------------------------------------------------------------
@files_bp.route("/<room>", methods=["DELETE"])
def clear_files(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        rows = conn.execute(
            "SELECT id FROM room_files WHERE room_id = ?", (room,)
        ).fetchall()
        conn.execute("DELETE FROM room_files WHERE room_id = ?", (room,))

    room_dir = _room_dir(room)
    for r in rows:
        try:
            (room_dir / f"{r['id']}.bin").unlink()
        except FileNotFoundError:
            pass

    return jsonify({"deleted_count": len(rows)})
