"""Message translation (Phase 83).

Uses OpenAI when configured. Results are cached per-user (because
messages may be E2E-encrypted and each user has their own plaintext).

Endpoints:
    GET  /api/translate/available
    POST /api/translate/text        {text, target_lang, source_lang?}
    POST /api/translate/message     {kind, message_id, target_lang, text}
    GET  /api/translate/message?kind=&message_id=&target_lang=
"""
from __future__ import annotations
import json
import os
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .logging_config import get_logger

log = get_logger("web.translate")

translate_bp = Blueprint("translate", __name__, url_prefix="/api/translate")

LANG_RE = re.compile(r"^[a-z]{2}(-[A-Za-z]{2,4})?$")
VALID_KINDS = {"chat", "dm", "group"}
MAX_TEXT = 4000
_MODEL = os.environ.get("TRANSLATE_MODEL", "gpt-4o-mini")


def _openai_available() -> bool:
    if not os.environ.get("OPENAI_API_KEY"):
        return False
    try:
        import openai  # noqa: F401
        return True
    except ImportError:
        return False


def _translate(text: str, target_lang: str, source_lang: str = None):
    """Call OpenAI. Returns (translated_text, detected_source_lang)."""
    from openai import OpenAI
    client = OpenAI()

    sys_prompt = (
        "You are a translation engine. Translate the user's text "
        f"into {target_lang}. Preserve formatting, line breaks, and emoji. "
        "Return ONLY a JSON object: "
        '{"translation": "...", "detected_source_lang": "xx"}.'
    )
    user_msg = text
    if source_lang:
        user_msg = f"[from {source_lang}]\n{text}"

    resp = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    payload = json.loads(resp.choices[0].message.content)
    return payload.get("translation", ""), payload.get("detected_source_lang", "")


@translate_bp.route("/available", methods=["GET"])
def available():
    return jsonify({
        "available": _openai_available(),
        "model": _MODEL if _openai_available() else None,
    })


@translate_bp.route("/text", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def translate_text():
    if not _openai_available():
        return jsonify({"error": "Translation not configured on this server"}), 503

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    target_lang = (data.get("target_lang") or "").strip()
    source_lang = (data.get("source_lang") or "").strip() or None

    if not text or not target_lang:
        return jsonify({"error": "text and target_lang required"}), 400
    if len(text.encode("utf-8")) > MAX_TEXT:
        return jsonify({"error": f"text too long (max {MAX_TEXT} bytes)"}), 400
    if not LANG_RE.match(target_lang):
        return jsonify({"error": "Invalid target_lang (e.g. 'en', 'fr', 'pt-BR')"}), 400

    try:
        translated, detected = _translate(text, target_lang, source_lang)
    except Exception as e:
        log.warning("translate failed: %s", e)
        return jsonify({"error": f"Translation failed: {e}"}), 500

    return jsonify({
        "translation": translated,
        "target_lang": target_lang,
        "detected_source_lang": detected,
    })


@translate_bp.route("/message", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def translate_message():
    """Translate a message body supplied by the client.

    The client decrypts (if needed) and sends plaintext. We translate
    and cache the result PER USER so encrypted messages stay private
    to the requesting user's translations.
    """
    if not _openai_available():
        return jsonify({"error": "Translation not configured on this server"}), 503

    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip().lower()
    message_id = data.get("message_id")
    target_lang = (data.get("target_lang") or "").strip()
    text = (data.get("text") or "").strip()

    if kind not in VALID_KINDS:
        return jsonify({"error": f"kind must be one of {sorted(VALID_KINDS)}"}), 400
    if not isinstance(message_id, int):
        return jsonify({"error": "message_id must be an integer"}), 400
    if not target_lang or not LANG_RE.match(target_lang):
        return jsonify({"error": "Invalid target_lang"}), 400
    if not text:
        return jsonify({"error": "text required"}), 400
    if len(text.encode("utf-8")) > MAX_TEXT:
        return jsonify({"error": "text too long"}), 400

    # Check cache
    with get_db() as conn:
        row = conn.execute("""
            SELECT translated_body, source_lang, provider
            FROM message_translations
            WHERE user_id = ? AND message_kind = ? AND message_id = ? AND target_lang = ?
        """, (g.user_id, kind, message_id, target_lang)).fetchone()
        if row:
            return jsonify({
                "translation": row["translated_body"],
                "target_lang": target_lang,
                "detected_source_lang": row["source_lang"],
                "cached": True,
            })

    # Translate
    try:
        translated, detected = _translate(text, target_lang)
    except Exception as e:
        log.warning("translate_message failed: %s", e)
        return jsonify({"error": f"Translation failed: {e}"}), 500

    # Cache
    with get_db() as conn:
        conn.execute("""
            INSERT INTO message_translations
            (user_id, message_kind, message_id, target_lang, source_lang,
             translated_body, provider)
            VALUES (?, ?, ?, ?, ?, ?, 'openai')
            ON CONFLICT(user_id, message_kind, message_id, target_lang) DO UPDATE SET
                translated_body = excluded.translated_body,
                source_lang = excluded.source_lang,
                created_at = CURRENT_TIMESTAMP
        """, (g.user_id, kind, message_id, target_lang, detected, translated))

    return jsonify({
        "translation": translated,
        "target_lang": target_lang,
        "detected_source_lang": detected,
        "cached": False,
    })


@translate_bp.route("/message", methods=["GET"])
@require_auth
def get_cached_translation():
    kind = (request.args.get("kind") or "").strip().lower()
    target_lang = (request.args.get("target_lang") or "").strip()
    try:
        message_id = int(request.args.get("message_id", 0))
    except ValueError:
        return jsonify({"error": "message_id must be an integer"}), 400

    if kind not in VALID_KINDS:
        return jsonify({"error": f"kind must be one of {sorted(VALID_KINDS)}"}), 400
    if not target_lang:
        return jsonify({"error": "target_lang required"}), 400

    with get_db() as conn:
        row = conn.execute("""
            SELECT translated_body, source_lang, created_at
            FROM message_translations
            WHERE user_id = ? AND message_kind = ? AND message_id = ? AND target_lang = ?
        """, (g.user_id, kind, message_id, target_lang)).fetchone()

    if not row:
        return jsonify({"cached": False})
    return jsonify({
        "cached": True,
        "translation": row["translated_body"],
        "target_lang": target_lang,
        "detected_source_lang": row["source_lang"],
        "created_at": row["created_at"],
    })
