"""Media gallery (Phase 45).

A unified view of everything shared in a room: uploaded files, voice
clips, and reference images. Returns metadata only — blobs are fetched
via the existing file/voice endpoints.

    GET /api/rooms/<room>/media?kind=file|voice|all&limit=200
"""
from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth

media_bp = Blueprint("media", __name__, url_prefix="/api/rooms")


def _row_to_item(row, kind):
    d = dict(row)
    d["kind"] = kind
    return d


@media_bp.route("/<room>/media", methods=["GET"])
@require_auth
def room_media(room):
    kind_filter = (request.args.get("kind") or "all").lower()
    if kind_filter not in ("all", "file", "voice"):
        return jsonify({"error": "kind must be all|file|voice"}), 400
    try:
        limit = min(int(request.args.get("limit", 200)), 500)
    except ValueError:
        limit = 200

    files, voices = [], []

    with get_db() as conn:
        if kind_filter in ("all", "file"):
            rows = conn.execute("""
                SELECT id, filename, size_bytes, encrypted, uploaded_by AS username,
                       created_at
                FROM room_files
                WHERE room_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (room, limit)).fetchall()
            files = [_row_to_item(r, "file") for r in rows]

        if kind_filter in ("all", "voice"):
            # voice_clips now has a room_id column (Phase 41 schema_extras)
            try:
                rows = conn.execute("""
                    SELECT id, duration_ms, size_bytes, mime, encrypted,
                           uploader AS username, created_at
                    FROM voice_clips
                    WHERE room_id = ?
                    ORDER BY created_at DESC LIMIT ?
                """, (room, limit)).fetchall()
            except Exception:
                # Older DBs without room_id column: filter via chat_messages attachments
                rows = conn.execute("""
                    SELECT v.id, v.duration_ms, v.size_bytes, v.mime, v.encrypted,
                           v.uploader AS username, v.created_at
                    FROM voice_clips v
                    JOIN chat_messages c ON c.attachment_id = v.id
                    WHERE c.room_id = ?
                    ORDER BY v.created_at DESC LIMIT ?
                """, (room, limit)).fetchall()
            voices = [_row_to_item(r, "voice") for r in rows]

    # Merge and sort newest first
    merged = files + voices
    merged.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return jsonify({
        "room": room,
        "kind": kind_filter,
        "items": merged,
        "counts": {
            "files": len(files),
            "voice": len(voices),
            "total": len(merged),
        },
    })
