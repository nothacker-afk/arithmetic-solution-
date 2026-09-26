"""Bot API (Phase 43).

A bot is a room-scoped entity with a token. It can POST messages to the
room via `POST /api/bots/<bot_id>/messages` with an `Authorization: Bot <token>`
header. Commands: help, echo, time, roll, 8ball.

Endpoints (owner/auth):
    POST   /api/bots                          {room_id, name}     create → returns token (once)
    GET    /api/bots                          list my bots
    DELETE /api/bots/<bot_id>                 delete bot

Endpoints (bot token):
    POST   /api/bots/<bot_id>/messages        {body}              post as bot
    GET    /api/bots/me                       bot info
"""
import hashlib
import json
import random
import re
import secrets
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

bots_bp = Blueprint("bots", __name__, url_prefix="/api/bots")

BOT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
DEFAULT_COMMANDS = ["help", "echo", "time", "roll", "8ball"]


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _verify_bot(token: str):
    if not token:
        return None
    h = _hash_token(token)
    with get_db() as conn:
        return conn.execute(
            "SELECT id, room_id, name, commands FROM bots WHERE token_hash = ?", (h,)
        ).fetchone()


# ---------------------------------------------------------------------
# Handle a command -> response body
# ---------------------------------------------------------------------
def _handle_command(cmd_line: str, bot_name: str) -> str:
    parts = cmd_line.strip().split(maxsplit=1)
    cmd = parts[0].lstrip("!").lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "help":
        return ("Commands: `!help` · `!echo <text>` · `!time` · "
                "`!roll [max]` · `!8ball <question>`")
    if cmd == "echo":
        return arg or "(nothing to echo)"
    if cmd == "time":
        return datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    if cmd == "roll":
        try:
            sides = int(arg) if arg else 6
            sides = max(2, min(sides, 1000))
        except ValueError:
            sides = 6
        return f"🎲 {random.randint(1, sides)} (1..{sides})"
    if cmd == "8ball":
        answers = [
            "It is certain.", "Without a doubt.", "Yes.",
            "Most likely.", "Ask again later.", "Cannot predict now.",
            "Don't count on it.", "My reply is no.", "Very doubtful.",
        ]
        return random.choice(answers) + (" — " + arg if arg else "")
    return f"Unknown command: !{cmd}. Try `!help`."


# ---------------------------------------------------------------------
# Bot token auth helper
# ---------------------------------------------------------------------
def _require_bot_token(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bot "):
            return jsonify({"error": "Missing Bot token"}), 401
        token = header[4:].strip()
        bot = _verify_bot(token)
        if not bot:
            return jsonify({"error": "Invalid bot token"}), 401
        g.bot = bot
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------
# Management (user-authenticated)
# ---------------------------------------------------------------------
@bots_bp.route("", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def create_bot():
    data = request.get_json(silent=True) or {}
    room_id = (data.get("room_id") or "").strip()
    name = (data.get("name") or "").strip()[:48]
    if not room_id or not name:
        return jsonify({"error": "room_id and name required"}), 400

    with get_db() as conn:
        # Only the room owner can create bots
        room = conn.execute("SELECT owner_id FROM rooms WHERE name = ?", (room_id,)).fetchone()
        if not room:
            return jsonify({"error": "Room not registered"}), 404
        if room["owner_id"] != g.user_id:
            return jsonify({"error": "Only the room owner can create bots"}), 403

        bot_id = uuid.uuid4().hex
        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)
        commands = ",".join(DEFAULT_COMMANDS)

        conn.execute(
            "INSERT INTO bots (id, room_id, name, token_hash, commands, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (bot_id, room_id, name, token_hash, commands, g.user_id),
        )

    log_event("bot.create", actor_id=g.user_id, resource="bot",
              resource_id=bot_id, details={"room_id": room_id, "name": name})

    return jsonify({
        "id": bot_id,
        "room_id": room_id,
        "name": name,
        "token": token,   # shown ONCE — client must save it
        "commands": DEFAULT_COMMANDS,
    }), 201


@bots_bp.route("", methods=["GET"])
@require_auth
def list_bots():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT b.id, b.room_id, b.name, b.commands,
                   b.created_at, b.last_seen_at
            FROM bots b
            WHERE b.created_by = ?
            ORDER BY b.created_at DESC
        """, (g.user_id,)).fetchall()
    return jsonify({"bots": [dict(r) for r in rows]})


@bots_bp.route("/<bot_id>", methods=["DELETE"])
@require_auth
def delete_bot(bot_id):
    if not BOT_ID_RE.match(bot_id):
        return jsonify({"error": "Invalid bot id"}), 400
    with get_db() as conn:
        row = conn.execute("SELECT created_by FROM bots WHERE id = ?", (bot_id,)).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if row["created_by"] != g.user_id:
            return jsonify({"error": "Only the creator can delete"}), 403
        conn.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
    log_event("bot.delete", actor_id=g.user_id, resource="bot", resource_id=bot_id)
    return jsonify({"deleted": bot_id})


# ---------------------------------------------------------------------
# Bot endpoints (bot-token authenticated)
# ---------------------------------------------------------------------
@bots_bp.route("/me", methods=["GET"])
@_require_bot_token
def bot_me():
    bot = g.bot
    return jsonify({
        "id": bot["id"],
        "room_id": bot["room_id"],
        "name": bot["name"],
        "commands": bot["commands"].split(","),
    })


@bots_bp.route("/<bot_id>/messages", methods=["POST"])
@_require_bot_token
@rate_limit(max_calls=60, window_seconds=60)
def bot_post(bot_id):
    bot = g.bot
    if bot["id"] != bot_id:
        return jsonify({"error": "Token does not match bot id"}), 403

    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "body required"}), 400

    # Handle commands (first non-empty line starting with !)
    first = body.split("\n", 1)[0].strip()
    if first.startswith("!"):
        body = _handle_command(first, bot["name"])

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO chat_messages (room_id, username, body, encrypted, kind) "
            "VALUES (?, ?, ?, 0, 'text')",
            (bot["room_id"], bot["name"], body),
        )
        msg_id = cur.lastrowid
        conn.execute("UPDATE bots SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ?",
                     (bot_id,))
        row = conn.execute(
            "SELECT id, username, body, encrypted, kind, created_at "
            "FROM chat_messages WHERE id = ?", (msg_id,),
        ).fetchone()

    # Broadcast over WebSocket
    try:
        from .realtime import socketio
        socketio.emit("chat_message", {
            "id": msg_id, "username": bot["name"], "body": body,
            "encrypted": False, "kind": "text",
        }, to=bot["room_id"])
    except Exception:
        pass

    return jsonify(dict(row)), 201
