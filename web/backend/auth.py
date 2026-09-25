"""JWT-based authentication blueprint."""
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

from .config import Config
from .database import get_db


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _make_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=Config.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)


def require_auth(f):
    """Decorator: verify Bearer token and set g.user_id."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "Missing Bearer token"}), 401
        token = header[7:].strip()
        try:
            payload = jwt.decode(
                token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM]
            )
            g.user_id = int(payload["sub"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except (jwt.InvalidTokenError, KeyError, ValueError):
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return wrapper


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"error": "username, email, password required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if "@" not in email:
        return jsonify({"error": "Invalid email"}), 400
    if len(password) < Config.MIN_PASSWORD_LENGTH:
        return jsonify({
            "error": f"Password must be at least {Config.MIN_PASSWORD_LENGTH} characters"
        }), 400

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email),
        ).fetchone()
        if existing:
            return jsonify({"error": "Username or email already taken"}), 409

        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, generate_password_hash(password)),
        )
        user_id = cur.lastrowid

    return jsonify({
        "user_id": user_id,
        "username": username,
        "token": _make_token(user_id),
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({
        "user_id": row["id"],
        "username": row["username"],
        "token": _make_token(row["id"]),
    })


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, email, created_at FROM users WHERE id = ?",
            (g.user_id,),
        ).fetchone()
    if not row:
        return jsonify({"error": "User not found"}), 404
    return jsonify(dict(row))
