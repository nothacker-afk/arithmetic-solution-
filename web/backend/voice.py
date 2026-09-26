"""Voice clips (Phase 31).

Blobs are opaque on the server (E2E encrypted by the client). Metadata
lives in the `voice_clips` table.

Endpoints:
    POST   /api/voice           - upload a clip, returns {id}
    GET    /api/voice/<id>      - download blob
    DELETE /api/voice/<id>      - delete (uploader only)
    GET    /api/voice           - list my recent clips
"""
import base64
import os
import re
import uuid
from pathlib import Path

from flask import Blueprint, request, jsonify, send_file, g

from .config import Config
from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

voice_bp = Blueprint("voice", __name__, url_prefix="/api/voice")

VOICE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_VOICE_BYTES = int(os.environ.get("MAX_VOICE_BYTES", str(2 * 1024 * 1024)))  # 2 MB


def _voice_dir() -> Path:
    d = Path(Config.FILE_STORAGE_DIR).parent / "arithmetic_voice"
    d.mkdir(parents=True, exist_ok=True)
    return d


@voice_bp.route("", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def upload_voice():
    data = request.get_json(silent=True) or {}
    ciphertext_b64 = data.get("ciphertext_b64")
    duration_ms = int(data.get("duration_ms", 0))
    mime = (data.get("mime") or "audio/webm")[:64]
    encrypted = bool(data.get("encrypted", True))

    if not isinstance(ciphertext_b64, str) or not ciphertext_b64:
        return jsonify({"error": "ciphertext_b64 is required"}), 400
    try:
        blob = base64.b64decode(ciphertext_b64, validate=True)
    except Exception:
        return jsonify({"error": "ciphertext_b64 is not valid base64"}), 400
    if len(blob) > MAX_VOICE_BYTES:
        return jsonify({"error": f"Voice clip exceeds {MAX_VOICE_BYTES} byte limit"}), 413

    clip_id = uuid.uuid4().hex
    (_voice_dir() / f"{clip_id}.bin").write_bytes(blob)

    with get_db() as conn:
        me = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
        uploader = me["username"] if me else "unknown"
        conn.execute(
            "INSERT INTO voice_clips (id, uploader, duration_ms, size_bytes, mime, encrypted) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (clip_id, uploader, duration_ms, len(blob), mime, 1 if encrypted else 0),
        )

    return jsonify({
        "id": clip_id,
        "duration_ms": duration_ms,
        "size_bytes": len(blob),
        "mime": mime,
        "encrypted": encrypted,
    }), 201


@voice_bp.route("/<clip_id>", methods=["GET"])
def download_voice(clip_id):
    if not VOICE_ID_RE.match(clip_id):
        return jsonify({"error": "Invalid id"}), 400
    with get_db() as conn:
        row = conn.execute(
            "SELECT mime, encrypted FROM voice_clips WHERE id = ?", (clip_id,)
        ).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    path = _voice_dir() / f"{clip_id}.bin"
    if not path.exists():
        return jsonify({"error": "Blob missing"}), 410
    return send_file(str(path), mimetype="application/octet-stream",
                     as_attachment=False,
                     download_name=f"{clip_id}.webm")


@voice_bp.route("/<clip_id>", methods=["DELETE"])
@require_auth
def delete_voice(clip_id):
    if not VOICE_ID_RE.match(clip_id):
        return jsonify({"error": "Invalid id"}), 400
    with get_db() as conn:
        me = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
        row = conn.execute(
            "SELECT uploader FROM voice_clips WHERE id = ?", (clip_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if not me or row["uploader"] != me["username"]:
            return jsonify({"error": "Not the uploader"}), 403
        conn.execute("DELETE FROM voice_clips WHERE id = ?", (clip_id,))
    try:
        (_voice_dir() / f"{clip_id}.bin").unlink()
    except FileNotFoundError:
        pass
    return jsonify({"deleted": clip_id})


@voice_bp.route("", methods=["GET"])
@require_auth
def list_voice():
    with get_db() as conn:
        me = conn.execute("SELECT username FROM users WHERE id = ?", (g.user_id,)).fetchone()
        rows = conn.execute(
            "SELECT id, duration_ms, size_bytes, mime, created_at "
            "FROM voice_clips WHERE uploader = ? ORDER BY created_at DESC LIMIT 50",
            (me["username"] if me else "",),
        ).fetchall()
    return jsonify({"clips": [dict(r) for r in rows]})


@voice_bp.route("/<clip_id>/transcript", methods=["GET"])
def get_transcript(clip_id):
    """Return the cached transcript for a voice clip (if any)."""
    if not VOICE_ID_RE.match(clip_id):
        return jsonify({"error": "Invalid id"}), 400
    with get_db() as conn:
        row = conn.execute(
            "SELECT transcript, transcript_lang FROM voice_clips WHERE id = ?",
            (clip_id,),
        ).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "id": clip_id,
        "transcript": row["transcript"] or "",
        "language": row["transcript_lang"] or "",
    })
