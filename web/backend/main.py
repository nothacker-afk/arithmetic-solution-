"""Flask backend for Arithmetic Super App.

Termux-friendly (pure Python, no Rust/C compilation required).

Endpoints:
    GET  /                - serves the frontend
    GET  /api/health      - health check
    POST /api/basic       - basic operations
    POST /api/scientific  - scientific operations
    POST /api/matrix      - matrix operations
    POST /api/ai          - natural language parser
"""
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from .database import init_db
from .auth import auth_bp
from .history import history_bp
from .rate_limit import rate_limit
from .realtime import socketio
from .chat import chat_bp
from .files import files_bp
from .rooms import rooms_bp
from .i18n import supported_locales, TRANSLATIONS, pick_locale
from .theme import theme_bp
from .admin import admin_bp
from .admin_dashboard import admin_dash_bp
from .account import account_bp
from .notifications import notifications_bp
from .passkeys import passkeys_bp
from .search import search_bp, init_fts as _init_search
from .dms import dms_bp
from .tracing import setup_tracing, current_trace_id
from .jobs import start_if_enabled as _start_retention

from arithmetic import plugins
from arithmetic import (
    add, subtract, multiply, divide, power, modulo, floor_divide,
    sqrt, cbrt, log10, sin, cos, tan, factorial, absolute,
    matrix_add, matrix_subtract, matrix_multiply, matrix_transpose,
)

# AI engine (Phase 3) - import lazily so Phase 2 alone still works
try:
    from ai_engine import parse_and_solve, llm_solve, ParseError, is_llm_available
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False


FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app = Flask(__name__, static_folder=None)
CORS(app)

# Phase 6: bind SocketIO to the Flask app
socketio.init_app(app)

# Phase 4: register auth + history + init database
app.register_blueprint(auth_bp)
app.register_blueprint(history_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(files_bp)
app.register_blueprint(rooms_bp)
app.register_blueprint(theme_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(admin_dash_bp)
app.register_blueprint(account_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(passkeys_bp)
app.register_blueprint(search_bp)
app.register_blueprint(dms_bp)


BASIC_OPS = {
    "add": add, "subtract": subtract, "multiply": multiply, "divide": divide,
    "power": power, "modulo": modulo, "floor_divide": floor_divide,
}

SCIENTIFIC_OPS = {
    "sqrt": sqrt, "cbrt": cbrt, "log10": log10,
    "sin": sin, "cos": cos, "tan": tan,
    "factorial": factorial, "absolute": absolute,
}

MATRIX_OPS = {
    "matrix_add": matrix_add,
    "matrix_subtract": matrix_subtract,
    "matrix_multiply": matrix_multiply,
}


# -------------------------------------------------------------------------
# Frontend
# -------------------------------------------------------------------------
@app.route("/")
def index():
    if not FRONTEND_DIR.exists():
        return jsonify({"error": "Frontend not built"}), 404
    return send_from_directory(str(FRONTEND_DIR), "index.html")


# -------------------------------------------------------------------------
# Health
# -------------------------------------------------------------------------
@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "backend": "flask",
        "version": "0.3.0",
        "ai_available": AI_AVAILABLE,
    })


# -------------------------------------------------------------------------
# Basic
# -------------------------------------------------------------------------
@app.route("/api/basic", methods=["POST"])
@rate_limit(max_calls=120, window_seconds=60)
def basic():
    data = request.get_json(silent=True) or {}
    op = data.get("operation")
    if op not in BASIC_OPS:
        return jsonify({"error": f"Unknown operation: {op}"}), 400
    try:
        a = float(data.get("a"))
        b = float(data.get("b"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid numeric input"}), 400
    try:
        result = BASIC_OPS[op](a, b)
        return jsonify({"result": result, "expression": f"{a} {op} {b}"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# -------------------------------------------------------------------------
# Scientific
# -------------------------------------------------------------------------
@app.route("/api/scientific", methods=["POST"])
@rate_limit(max_calls=120, window_seconds=60)
def scientific():
    data = request.get_json(silent=True) or {}
    op = data.get("operation")
    if op not in SCIENTIFIC_OPS:
        return jsonify({"error": f"Unknown operation: {op}"}), 400
    try:
        x = float(data.get("x"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid numeric input"}), 400
    try:
        result = SCIENTIFIC_OPS[op](x)
        return jsonify({"result": result, "expression": f"{op}({x})"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# -------------------------------------------------------------------------
# Matrix
# -------------------------------------------------------------------------
@app.route("/api/matrix", methods=["POST"])
@rate_limit(max_calls=120, window_seconds=60)
def matrix():
    data = request.get_json(silent=True) or {}
    op = data.get("operation")
    a = data.get("a")
    b = data.get("b")
    try:
        if op == "matrix_transpose":
            result = matrix_transpose(a)
        elif op in MATRIX_OPS:
            if b is None:
                return jsonify({"error": "Matrix 'b' is required"}), 400
            result = MATRIX_OPS[op](a, b)
        else:
            return jsonify({"error": f"Unknown operation: {op}"}), 400
        return jsonify({"result": result, "expression": op})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# -------------------------------------------------------------------------
# AI (Phase 3)
# -------------------------------------------------------------------------
@app.route("/api/ai/status")
def ai_status():
    return jsonify({
        "ai_available": AI_AVAILABLE,
        "llm_available": is_llm_available() if AI_AVAILABLE else False,
        "engine": ("llm+rule" if (AI_AVAILABLE and is_llm_available()) else "rule") if AI_AVAILABLE else "none",
    })


@app.route("/api/ai", methods=["POST"])
@rate_limit(max_calls=120, window_seconds=60)
def ai_solve():
    if not AI_AVAILABLE:
        return jsonify({"error": "AI engine not installed (Phase 3 pending)"}), 503
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Empty input"}), 400
    try:
        use_llm = bool(data.get("use_llm")) and is_llm_available()
        result = llm_solve(text) if use_llm else parse_and_solve(text)
        return jsonify(result)
    except ParseError as e:
        return jsonify({"error": str(e)}), 400


# -------------------------------------------------------------------------
# Entrypoint
# -------------------------------------------------------------------------


# -------------------------------------------------------------------------
# Plugins (Phase 6)
# -------------------------------------------------------------------------
@app.route("/api/plugins", methods=["GET"])
def list_registered_plugins():
    return jsonify({"plugins": plugins.list_plugins()})


@app.route("/api/plugins/<name>", methods=["POST"])
def call_plugin(name):
    data = request.get_json(silent=True) or {}
    args = data.get("args", [])
    if not isinstance(args, list):
        return jsonify({"error": "args must be a list"}), 400
    try:
        result = plugins.call(name, *args)
        return jsonify({"plugin": name, "args": args, "result": result})
    except plugins.PluginError as e:
        return jsonify({"error": str(e)}), 400




# -------------------------------------------------------------------------
# Lazy DB initialization (avoids import-time side effects)
# -------------------------------------------------------------------------
_db_initialized = False


@app.before_request
def _ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        from .database import init_db
        init_db()
        _db_initialized = True


# -------------------------------------------------------------------------
# GraphQL (Phase 8) — Strawberry-mounted at /graphql
# -------------------------------------------------------------------------
from strawberry.flask.views import GraphQLView  # noqa: E402
from .graphql_schema import schema as _graphql_schema  # noqa: E402


app.add_url_rule(
    "/graphql",
    view_func=GraphQLView.as_view("graphql_view", schema=_graphql_schema),
)



# -------------------------------------------------------------------------
# PWA (Phase 8) — manifest, service worker, static assets
# -------------------------------------------------------------------------
@app.route("/manifest.json")
def manifest():
    return send_from_directory(str(FRONTEND_DIR), "manifest.json",
                               mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    resp = send_from_directory(str(FRONTEND_DIR), "sw.js",
                               mimetype="application/javascript")
    # Allow SW to control root scope
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(FRONTEND_DIR), filename)




# -------------------------------------------------------------------------
# i18n (Phase 12)
# -------------------------------------------------------------------------
@app.route("/api/i18n/locales")
def i18n_locales():
    return jsonify({"default": "en", "locales": supported_locales()})


@app.route("/api/i18n/<locale>")
def i18n_get(locale):
    locale = locale.lower()
    if locale not in TRANSLATIONS:
        return jsonify({"error": "Unsupported locale"}), 404
    return jsonify({"locale": locale, "strings": TRANSLATIONS[locale]})


@app.route("/api/i18n/detect")
def i18n_detect():
    """Return the locale best matching the client's Accept-Language."""
    picked = pick_locale(request.headers.get("Accept-Language", ""))
    return jsonify({"locale": picked})




@app.route("/admin")
def admin_page():
    """Serve the admin dashboard (Phase 16)."""
    path = FRONTEND_DIR / "admin.html"
    if not path.exists():
        return jsonify({"error": "Admin dashboard not installed"}), 404
    return send_from_directory(str(FRONTEND_DIR), "admin.html")




@app.route("/gallery")
def gallery():
    """Serve the component gallery (Phase 27)."""
    path = FRONTEND_DIR / "gallery.html"
    if not path.exists():
        return jsonify({"error": "Gallery not installed"}), 404
    return send_from_directory(str(FRONTEND_DIR), "gallery.html")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    sys.stderr.write(f"\n  Arithmetic Super App running at http://127.0.0.1:{port}\n")
    sys.stderr.write(f"  WebSocket: ws://127.0.0.1:{port}/socket.io/\n\n")
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
