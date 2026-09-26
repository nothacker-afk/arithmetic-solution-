"""WebAuthn / passkey support (Phase 25).

Requires the `webauthn` package. If not installed, every endpoint
returns 503 with a clear message, and the UI hides the passkey button.

    pip install webauthn
"""
import base64
import json
import os
import secrets
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g
from werkzeug.security import check_password_hash

from .auth import require_auth, _make_token
from .database import get_db
from .rate_limit import rate_limit
from .audit import log_event
from .logging_config import get_logger

log = get_logger("web.passkeys")

passkeys_bp = Blueprint("passkeys", __name__, url_prefix="/api/passkeys")


def _webauthn():
    try:
        import webauthn  # noqa: F401
        return webauthn
    except ImportError:
        return None


def _rp_id() -> str:
    return os.environ.get("WEBAUTHN_RP_ID", "localhost")


def _rp_name() -> str:
    return os.environ.get("WEBAUTHN_RP_NAME", "Arithmetic Super App")


def _expected_origin() -> str:
    return os.environ.get("WEBAUTHN_ORIGIN", "http://localhost:8000")


@passkeys_bp.route("/available", methods=["GET"])
def available():
    """Tell the frontend whether passkeys are enabled."""
    w = _webauthn()
    return jsonify({
        "available": w is not None,
        "rp_id": _rp_id(),
    })


def _store_challenge(user_id, challenge, kind: str) -> None:
    """Cache a challenge per user + kind. 5-minute TTL."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO passkey_challenges (user_id, kind, challenge, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, kind, challenge,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def _consume_challenge(user_id, kind: str) -> str | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT challenge FROM passkey_challenges WHERE user_id = ? AND kind = ?",
            (user_id, kind),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM passkey_challenges WHERE user_id = ? AND kind = ?",
                     (user_id, kind))
    return row["challenge"]


# ---------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------
@passkeys_bp.route("/register/begin", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def register_begin():
    w = _webauthn()
    if not w:
        return jsonify({"error": "Passkeys not installed on this server. "
                                 "Run: pip install webauthn"}), 503

    from webauthn.helpers.structs import (
        PublicKeyCredentialDescriptor, AuthenticatorSelectionCriteria,
    )
    from webauthn.helpers import generate_challenge

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (g.user_id,)
        ).fetchone()
        existing = conn.execute(
            "SELECT credential_id FROM passkeys WHERE user_id = ?", (g.user_id,)
        ).fetchall()

    exclude = [PublicKeyCredentialDescriptor(id=base64.urlsafe_b64decode(c["credential_id"] + "=="))
               for c in existing]

    options = w.generate_registration_options(
        rp_id=_rp_id(),
        rp_name=_rp_name(),
        user_id=str(user["id"]).encode(),
        user_name=user["username"],
        user_display_name=user["username"],
        exclude_credentials=exclude,
    )
    challenge = options.challenge
    if isinstance(challenge, bytes):
        challenge = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode()
    _store_challenge(g.user_id, challenge, "register")

    return jsonify({
        "challenge": challenge,
        "rp": {"id": _rp_id(), "name": _rp_name()},
        "user": {"id": str(user["id"]), "name": user["username"], "displayName": user["username"]},
        "pubKeyCredParams": [{"type": "public-key", "alg": -7}, {"type": "public-key", "alg": -257}],
        "timeout": 60000,
        "attestation": "none",
        "excludeCredentials": [{"type": "public-key", "id": c["credential_id"]} for c in existing],
    })


@passkeys_bp.route("/register/finish", methods=["POST"])
@require_auth
def register_finish():
    w = _webauthn()
    if not w:
        return jsonify({"error": "Passkeys not installed"}), 503

    data = request.get_json(silent=True) or {}
    credential = data.get("credential") or {}
    name = (data.get("name") or "passkey").strip()[:64]

    challenge = _consume_challenge(g.user_id, "register")
    if not challenge:
        return jsonify({"error": "Challenge expired or missing"}), 400

    try:
        verification = w.verify_registration_response(
            credential=credential,
            expected_challenge=challenge.encode() if isinstance(challenge, str) else challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_expected_origin(),
            require_user_verification=False,
        )
    except Exception as e:
        log.warning("passkey registration verify failed: %s", e)
        return jsonify({"error": f"Verification failed: {e}"}), 400

    credential_id = verification.credential_id
    if isinstance(credential_id, bytes):
        credential_id = base64.urlsafe_b64encode(credential_id).rstrip(b"=").decode()

    public_key = verification.credential_public_key
    if isinstance(public_key, bytes):
        public_key = base64.urlsafe_b64encode(public_key).rstrip(b"=").decode()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO passkeys (credential_id, user_id, public_key, sign_count, name) "
            "VALUES (?, ?, ?, ?, ?)",
            (credential_id, g.user_id, public_key, verification.sign_count, name),
        )

    log_event("passkey.register", actor_id=g.user_id, resource="passkey",
              resource_id=credential_id, details={"name": name})

    return jsonify({"registered": True, "credential_id": credential_id})


# ---------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------
@passkeys_bp.route("/login/begin", methods=["POST"])
@rate_limit(max_calls=20, window_seconds=60)
def login_begin():
    w = _webauthn()
    if not w:
        return jsonify({"error": "Passkeys not installed"}), 503

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "username is required"}), 400

    with get_db() as conn:
        user = conn.execute("SELECT id, username FROM users WHERE username = ?",
                            (username,)).fetchone()
        if not user:
            return jsonify({"error": "Unknown user"}), 404
        creds = conn.execute(
            "SELECT credential_id FROM passkeys WHERE user_id = ?", (user["id"],)
        ).fetchall()

    if not creds:
        return jsonify({"error": "No passkeys registered for this user"}), 404

    from webauthn.helpers import generate_challenge
    from webauthn.helpers.structs import PublicKeyCredentialDescriptor

    options = w.generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=[PublicKeyCredentialDescriptor(
            id=base64.urlsafe_b64decode(c["credential_id"] + "=="))
            for c in creds],
    )
    challenge = options.challenge
    if isinstance(challenge, bytes):
        challenge = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode()
    _store_challenge(user["id"], challenge, "login")

    return jsonify({
        "challenge": challenge,
        "rpId": _rp_id(),
        "timeout": 60000,
        "allowCredentials": [{"type": "public-key", "id": c["credential_id"]} for c in creds],
        "userVerification": "preferred",
        "user_id": user["id"],
    })


@passkeys_bp.route("/login/finish", methods=["POST"])
@rate_limit(max_calls=20, window_seconds=60)
def login_finish():
    w = _webauthn()
    if not w:
        return jsonify({"error": "Passkeys not installed"}), 503

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    credential = data.get("credential") or {}

    with get_db() as conn:
        user = conn.execute("SELECT id, username FROM users WHERE username = ?",
                            (username,)).fetchone()
        if not user:
            return jsonify({"error": "Unknown user"}), 404

    challenge = _consume_challenge(user["id"], "login")
    if not challenge:
        return jsonify({"error": "Challenge expired or missing"}), 400

    credential_id = credential.get("id") or credential.get("rawId")
    with get_db() as conn:
        row = conn.execute(
            "SELECT credential_id, public_key, sign_count FROM passkeys "
            "WHERE user_id = ? AND credential_id = ?",
            (user["id"], credential_id),
        ).fetchone()

    if not row:
        return jsonify({"error": "Credential not found"}), 401

    try:
        verification = w.verify_authentication_response(
            credential=credential,
            expected_challenge=challenge.encode() if isinstance(challenge, str) else challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_expected_origin(),
            credential_public_key=base64.urlsafe_b64decode(row["public_key"] + "=="),
            credential_current_sign_count=row["sign_count"],
            require_user_verification=False,
        )
    except Exception as e:
        log.warning("passkey login verify failed: %s", e)
        return jsonify({"error": f"Verification failed: {e}"}), 401

    with get_db() as conn:
        conn.execute("UPDATE passkeys SET sign_count = ?, last_used_at = ? "
                     "WHERE credential_id = ?",
                     (verification.new_sign_count,
                      datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      credential_id))

    token = _make_token(user["id"])
    log_event("passkey.login", actor_id=user["id"], resource="passkey",
              resource_id=credential_id)

    return jsonify({"token": token, "username": user["username"], "user_id": user["id"]})


# ---------------------------------------------------------------------
# Management
# ---------------------------------------------------------------------
@passkeys_bp.route("", methods=["GET"])
@require_auth
def list_passkeys():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT credential_id, name, created_at, last_used_at "
            "FROM passkeys WHERE user_id = ? ORDER BY created_at DESC",
            (g.user_id,),
        ).fetchall()
    return jsonify({"passkeys": [dict(r) for r in rows]})


@passkeys_bp.route("/<credential_id>", methods=["DELETE"])
@require_auth
def delete_passkey(credential_id):
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM passkeys WHERE credential_id = ? AND user_id = ?",
            (credential_id, g.user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not found"}), 404
    log_event("passkey.delete", actor_id=g.user_id, resource="passkey",
              resource_id=credential_id)
    return jsonify({"deleted": True})
