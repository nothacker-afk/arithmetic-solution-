"""Custom emoji packs (Phase 61).

Rooms can own custom emoji packs. Public packs are shared globally,
room-scoped packs only within that room.

Endpoints:
    GET    /api/emoji_packs                          list packs visible to me
    GET    /api/emoji_packs/<pack_id>                pack detail with items
    POST   /api/emoji_packs                          {name, room_id?, is_public?}
    DELETE /api/emoji_packs/<pack_id>
    POST   /api/emoji_packs/<pack_id>/items          {name, emoji?, image_url?}
    DELETE /api/emoji_packs/<pack_id>/items/<name>
"""
import re
import uuid

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

emoji_bp = Blueprint("emoji_packs", __name__, url_prefix="/api/emoji_packs")

PACK_ID_RE = re.compile(r"^[0-9a-f]{32}$")
ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
ITEM_NAME_RE = re.compile(r"^[a-z0-9_]{2,32}$")
MAX_ITEMS = 100


def _validate_pack_id(pid):
    if not PACK_ID_RE.match(pid or ""):
        raise ValueError("Invalid pack id")
    return pid


def _is_owner(conn, pack_id, user_id):
    row = conn.execute("SELECT created_by FROM emoji_packs WHERE id = ?", (pack_id,)).fetchone()
    return row and row["created_by"] == user_id


@emoji_bp.route("", methods=["GET"])
@require_auth
def list_packs():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT p.id, p.name, p.room_id, p.is_public, p.created_by,
                   p.created_at,
                   (SELECT COUNT(*) FROM emoji_pack_items WHERE pack_id = p.id) AS item_count
            FROM emoji_packs p
            WHERE p.is_public = 1 OR p.room_id IS NULL OR p.created_by = ?
            ORDER BY p.is_public DESC, p.name
        """, (g.user_id,)).fetchall()
    return jsonify({"packs": [dict(r) for r in rows]})


@emoji_bp.route("/<pack_id>", methods=["GET"])
@require_auth
def get_pack(pack_id):
    try:
        pack_id = _validate_pack_id(pack_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        pack = conn.execute(
            "SELECT id, name, room_id, is_public, created_by, created_at "
            "FROM emoji_packs WHERE id = ?", (pack_id,),
        ).fetchone()
        if not pack:
            return jsonify({"error": "Pack not found"}), 404
        items = conn.execute(
            "SELECT name, emoji, image_url FROM emoji_pack_items "
            "WHERE pack_id = ? ORDER BY name", (pack_id,),
        ).fetchall()
    out = dict(pack)
    out["items"] = [dict(r) for r in items]
    return jsonify(out)


@emoji_bp.route("", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def create_pack():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()[:64]
    room_id = (data.get("room_id") or "").strip() or None
    is_public = 1 if data.get("is_public") else 0

    if not name:
        return jsonify({"error": "name required"}), 400
    if room_id and not ROOM_RE.match(room_id):
        return jsonify({"error": "Invalid room name"}), 400

    with get_db() as conn:
        if room_id:
            # Only the room owner can create room-scoped packs
            row = conn.execute("SELECT owner_id FROM rooms WHERE name = ?", (room_id,)).fetchone()
            if row and row["owner_id"] != g.user_id:
                return jsonify({"error": "Only the room owner can create packs for this room"}), 403

        pack_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO emoji_packs (id, room_id, name, created_by, is_public) "
            "VALUES (?, ?, ?, ?, ?)",
            (pack_id, room_id, name, g.user_id, is_public),
        )

    log_event("emoji.create", actor_id=g.user_id, resource="emoji_pack",
              resource_id=pack_id, details={"name": name, "public": bool(is_public)})
    return jsonify({"id": pack_id, "name": name, "room_id": room_id,
                    "is_public": bool(is_public)}), 201


@emoji_bp.route("/<pack_id>", methods=["DELETE"])
@require_auth
def delete_pack(pack_id):
    try:
        pack_id = _validate_pack_id(pack_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        if not _is_owner(conn, pack_id, g.user_id):
            return jsonify({"error": "Only the creator can delete"}), 403
        conn.execute("DELETE FROM emoji_pack_items WHERE pack_id = ?", (pack_id,))
        conn.execute("DELETE FROM emoji_packs WHERE id = ?", (pack_id,))
    log_event("emoji.delete", actor_id=g.user_id, resource="emoji_pack", resource_id=pack_id)
    return jsonify({"deleted": pack_id})


@emoji_bp.route("/<pack_id>/items", methods=["POST"])
@require_auth
@rate_limit(max_calls=60, window_seconds=60)
def add_item(pack_id):
    try:
        pack_id = _validate_pack_id(pack_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip().lower()
    emoji = (data.get("emoji") or "").strip()[:16] or None
    image_url = (data.get("image_url") or "").strip()[:500] or None

    if not ITEM_NAME_RE.match(name):
        return jsonify({"error": "name must be 2-32 chars: a-z, 0-9, _"}), 400
    if not emoji and not image_url:
        return jsonify({"error": "either emoji or image_url required"}), 400

    with get_db() as conn:
        if not _is_owner(conn, pack_id, g.user_id):
            return jsonify({"error": "Only the pack creator can add items"}), 403
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM emoji_pack_items WHERE pack_id = ?", (pack_id,),
        ).fetchone()["n"]
        if count >= MAX_ITEMS:
            return jsonify({"error": f"item limit reached ({MAX_ITEMS})"}), 409
        try:
            conn.execute(
                "INSERT INTO emoji_pack_items (pack_id, name, emoji, image_url) "
                "VALUES (?, ?, ?, ?)", (pack_id, name, emoji, image_url),
            )
        except Exception:
            return jsonify({"error": "item name already exists in this pack"}), 409

    return jsonify({"pack_id": pack_id, "name": name, "emoji": emoji,
                    "image_url": image_url}), 201


@emoji_bp.route("/<pack_id>/items/<name>", methods=["DELETE"])
@require_auth
def remove_item(pack_id, name):
    try:
        pack_id = _validate_pack_id(pack_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with get_db() as conn:
        if not _is_owner(conn, pack_id, g.user_id):
            return jsonify({"error": "Only the pack creator can remove items"}), 403
        cur = conn.execute(
            "DELETE FROM emoji_pack_items WHERE pack_id = ? AND name = ?",
            (pack_id, name.lower()),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Item not found"}), 404
    return jsonify({"deleted": name})
