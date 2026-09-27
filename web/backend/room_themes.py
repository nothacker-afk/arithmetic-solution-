"""Room-level custom themes (Phase 81).

Each room can have a custom accent color, secondary color, banner
image, and emoji. Applied to chat UI when a room is active.

Endpoints:
    GET    /api/rooms/<room>/theme
    PUT    /api/rooms/<room>/theme       {accent?, accent_2?, banner_url?, emoji?, background?, font_family?}
    DELETE /api/rooms/<room>/theme       reset to default
"""
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

themes_bp = Blueprint("room_themes", __name__, url_prefix="/api/rooms")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")
URL_RE = re.compile(r"^https?://.{1,500}$")


def _validate_room(room):
    if not ROOM_RE.match(room or ""):
        raise ValueError("Invalid room name")
    return room


def _is_owner(conn, room, user_id):
    row = conn.execute("SELECT owner_id FROM rooms WHERE name = ?", (room,)).fetchone()
    return row and row["owner_id"] == user_id


DEFAULT_THEME = {
    "accent": None,
    "accent_2": None,
    "banner_url": None,
    "emoji": None,
    "background": None,
    "font_family": None,
    "is_custom": False,
}


@themes_bp.route("/<room>/theme", methods=["GET"])
@require_auth
def get_theme(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        row = conn.execute("""
            SELECT accent, accent_2, banner_url, emoji, background,
                   font_family, updated_at
            FROM room_themes WHERE room_id = ?
        """, (room,)).fetchone()

    if not row:
        return jsonify({"room": room, **DEFAULT_THEME})
    return jsonify({
        "room": room,
        "accent": row["accent"],
        "accent_2": row["accent_2"],
        "banner_url": row["banner_url"],
        "emoji": row["emoji"],
        "background": row["background"],
        "font_family": row["font_family"],
        "updated_at": row["updated_at"],
        "is_custom": True,
    })


@themes_bp.route("/<room>/theme", methods=["PUT"])
@require_auth
@rate_limit(max_calls=20, window_seconds=60)
def set_theme(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    accent = (data.get("accent") or "").strip() or None
    accent_2 = (data.get("accent_2") or "").strip() or None
    banner_url = (data.get("banner_url") or "").strip() or None
    emoji = (data.get("emoji") or "").strip()[:8] or None
    background = (data.get("background") or "").strip() or None
    font_family = (data.get("font_family") or "").strip()[:64] or None

    for name, val in (("accent", accent), ("accent_2", accent_2),
                      ("background", background)):
        if val and not COLOR_RE.match(val):
            return jsonify({
                "error": f"{name} must be a hex color like #38bdf8"
            }), 400
    if banner_url and not URL_RE.match(banner_url):
        return jsonify({"error": "banner_url must be an http(s) URL"}), 400

    with get_db() as conn:
        if not _is_owner(conn, room, g.user_id):
            return jsonify({"error": "Only the room owner can customize the theme"}), 403
        conn.execute("""
            INSERT INTO room_themes
            (room_id, accent, accent_2, banner_url, emoji, background, font_family, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                accent = excluded.accent,
                accent_2 = excluded.accent_2,
                banner_url = excluded.banner_url,
                emoji = excluded.emoji,
                background = excluded.background,
                font_family = excluded.font_family,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = excluded.updated_by
        """, (room, accent, accent_2, banner_url, emoji, background, font_family, g.user_id))

    log_event("room.theme.set", actor_id=g.user_id, resource="room",
              resource_id=room, details={"accent": accent, "emoji": emoji})

    return jsonify({
        "room": room,
        "accent": accent,
        "accent_2": accent_2,
        "banner_url": banner_url,
        "emoji": emoji,
        "background": background,
        "font_family": font_family,
        "is_custom": True,
    })


@themes_bp.route("/<room>/theme", methods=["DELETE"])
@require_auth
def reset_theme(room):
    try:
        room = _validate_room(room)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with get_db() as conn:
        # Room must exist and be claimed
        room_row = conn.execute(
            "SELECT owner_id FROM rooms WHERE name = ?", (room,),
        ).fetchone()
        if not room_row:
            return jsonify({"error": "Room not found"}), 404
        if room_row["owner_id"] != g.user_id:
            return jsonify({"error": "Only the room owner can reset the theme"}), 403
        cur = conn.execute("DELETE FROM room_themes WHERE room_id = ?", (room,))
        if cur.rowcount == 0:
            return jsonify({"error": "No custom theme to reset"}), 404

    log_event("room.theme.reset", actor_id=g.user_id, resource="room", resource_id=room)
    return jsonify({"reset": True, "room": room})
