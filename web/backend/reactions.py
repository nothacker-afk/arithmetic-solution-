"""Message reactions (Phase 32).

Emoji reactions on chat or DM messages. Kind is 'chat' or 'dm'.

Endpoints:
    GET    /api/reactions?kind=<k>&message_ids=1,2,3
    POST   /api/reactions                     {kind, message_id, emoji}
    DELETE /api/reactions                     {kind, message_id, emoji}
"""
from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

reactions_bp = Blueprint("reactions", __name__, url_prefix="/api/reactions")

# Fixed palette (client uses same list)
ALLOWED_EMOJI = {"👍", "❤️", "😂", "🎉", "🔥", "👀"}
VALID_KINDS = {"chat", "dm"}


@reactions_bp.route("", methods=["GET"])
@require_auth
def list_reactions():
    kind = (request.args.get("kind") or "").lower()
    if kind not in VALID_KINDS:
        return jsonify({"error": "kind must be 'chat' or 'dm'"}), 400
    ids_raw = request.args.get("message_ids") or ""
    try:
        ids = [int(x) for x in ids_raw.split(",") if x.strip()]
    except ValueError:
        return jsonify({"error": "invalid message_ids"}), 400
    if not ids:
        return jsonify({"reactions": {}})
    if len(ids) > 200:
        return jsonify({"error": "max 200 message ids"}), 400

    placeholders = ",".join("?" for _ in ids)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT message_id, user_id, emoji FROM message_reactions "
            f"WHERE message_kind = ? AND message_id IN ({placeholders})",
            (kind, *ids),
        ).fetchall()

    # {message_id: {emoji: [user_ids]}}
    out: dict = {i: {} for i in ids}
    for r in rows:
        out[r["message_id"]].setdefault(r["emoji"], []).append(r["user_id"])
    return jsonify({"reactions": out})


@reactions_bp.route("", methods=["POST"])
@require_auth
@rate_limit(max_calls=120, window_seconds=60)
def add_reaction():
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").lower()
    message_id = data.get("message_id")
    emoji = (data.get("emoji") or "").strip()

    if kind not in VALID_KINDS:
        return jsonify({"error": "kind must be 'chat' or 'dm'"}), 400
    if not isinstance(message_id, int):
        return jsonify({"error": "message_id must be an integer"}), 400
    if emoji not in ALLOWED_EMOJI:
        return jsonify({"error": "emoji not in allowed palette"}), 400

    with get_db() as conn:
        # Validate the target message exists
        if kind == "chat":
            exists = conn.execute("SELECT 1 FROM chat_messages WHERE id = ?", (message_id,)).fetchone()
        else:
            exists = conn.execute("SELECT 1 FROM dm_messages WHERE id = ?", (message_id,)).fetchone()
        if not exists:
            return jsonify({"error": "message not found"}), 404

        try:
            conn.execute(
                "INSERT INTO message_reactions (message_kind, message_id, user_id, emoji) "
                "VALUES (?, ?, ?, ?)",
                (kind, message_id, g.user_id, emoji),
            )
        except Exception:
            # UNIQUE constraint — already reacted; treat as success (idempotent)
            pass

    return jsonify({"ok": True, "kind": kind, "message_id": message_id, "emoji": emoji}), 201


@reactions_bp.route("", methods=["DELETE"])
@require_auth
def remove_reaction():
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").lower()
    message_id = data.get("message_id")
    emoji = (data.get("emoji") or "").strip()

    if kind not in VALID_KINDS or not isinstance(message_id, int):
        return jsonify({"error": "invalid kind or message_id"}), 400

    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM message_reactions "
            "WHERE message_kind = ? AND message_id = ? AND user_id = ? AND emoji = ?",
            (kind, message_id, g.user_id, emoji),
        )
    return jsonify({"removed": cur.rowcount})
