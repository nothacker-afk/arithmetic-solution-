"""Theme + language preference endpoints (JWT-protected)."""
from flask import Blueprint, request, jsonify, g

from .auth import require_auth
from .database import get_db
from .i18n import supported_locales

theme_bp = Blueprint("theme", __name__, url_prefix="/api/prefs")

VALID_THEMES = {"light", "dark", "auto"}


@theme_bp.route("", methods=["GET"])
@require_auth
def get_prefs():
    with get_db() as conn:
        row = conn.execute(
            "SELECT theme, language FROM user_preferences WHERE user_id = ?",
            (g.user_id,),
        ).fetchone()
    if not row:
        return jsonify({"theme": "auto", "language": "en"})
    return jsonify({"theme": row["theme"], "language": row["language"]})


@theme_bp.route("", methods=["PUT"])
@require_auth
def set_prefs():
    data = request.get_json(silent=True) or {}
    theme = (data.get("theme") or "auto").lower()
    language = (data.get("language") or "en").lower()

    if theme not in VALID_THEMES:
        return jsonify({"error": f"theme must be one of {sorted(VALID_THEMES)}"}), 400
    if language not in supported_locales():
        return jsonify({
            "error": f"language must be one of {supported_locales()}"
        }), 400

    with get_db() as conn:
        conn.execute(
            "INSERT INTO user_preferences (user_id, theme, language) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET theme = excluded.theme, "
            "language = excluded.language",
            (g.user_id, theme, language),
        )
    return jsonify({"theme": theme, "language": language})
