"""Push notifications via FCM HTTP v1 (Phase 19).

Design:
  - Silently no-ops when FCM credentials are not configured.
  - Uses only stdlib (urllib) — no google-auth or firebase-admin required.
  - Real production use: set FCM_SERVICE_ACCOUNT_JSON and FCM_ACCESS_TOKEN,
    or plug in a token-refresh callback (see `set_token_refresher`).

Endpoints:
    POST   /api/notifications/register      — store an FCM device token
    POST   /api/notifications/unregister    — remove a device token
    GET    /api/notifications/tokens        — list current user's tokens
    POST   /api/notifications/test          — send a test push
"""
import json
import os
import urllib.error
import urllib.request
from typing import Callable, Optional

from flask import Blueprint, request, jsonify, g

from .auth import require_auth
from .database import get_db
from .rate_limit import rate_limit
from .logging_config import get_logger

log = get_logger("web.notifications")

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"

# Optional plug-in callback for token refresh (e.g., from google.auth)
_token_refresher: Optional[Callable[[], Optional[str]]] = None


def set_token_refresher(fn: Callable[[], Optional[str]]) -> None:
    """Register a callable that returns a fresh FCM access token, or None."""
    global _token_refresher
    _token_refresher = fn


def _credentials():
    """Return (project_id, access_token) or (None, None)."""
    cfg_path = os.environ.get("FCM_SERVICE_ACCOUNT_JSON")
    project_id = None
    if cfg_path and os.path.exists(cfg_path):
        try:
            with open(cfg_path) as f:
                project_id = json.load(f).get("project_id")
        except Exception as e:
            log.warning("FCM service-account read failed: %s", e)
    # Env-var project id also works if the service-account file isn't used
    project_id = project_id or os.environ.get("FCM_PROJECT_ID")
    token = os.environ.get("FCM_ACCESS_TOKEN")
    if not token and _token_refresher:
        try:
            token = _token_refresher()
        except Exception as e:
            log.warning("token refresher failed: %s", e)
    return project_id, token


def send_push(user_id: int, title: str, body: str, data: Optional[dict] = None) -> bool:
    """Best-effort delivery. Returns True if at least one push was accepted."""
    project, token = _credentials()
    if not project or not token:
        log.info("push (dry-run) user=%s title=%r body=%r", user_id, title, body)
        return False

    with get_db() as conn:
        tokens = [r["token"] for r in conn.execute(
            "SELECT token FROM device_tokens WHERE user_id = ?", (user_id,)
        ).fetchall()]
    if not tokens:
        return False

    url = FCM_ENDPOINT.format(project=project)
    sent = 0
    stale = []
    for device_token in tokens:
        payload = {
            "message": {
                "token": device_token,
                "notification": {"title": title, "body": body},
                "data": {k: str(v) for k, v in (data or {}).items()},
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    sent += 1
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):  # token no longer valid
                stale.append(device_token)
            else:
                log.warning("push HTTP %s: %s", e.code, e.reason)
        except Exception as e:
            log.warning("push send error: %s", e)

    # Prune stale tokens
    if stale:
        with get_db() as conn:
            for t in stale:
                conn.execute("DELETE FROM device_tokens WHERE token = ?", (t,))
        log.info("pruned %d stale device tokens", len(stale))

    return sent > 0


# ---------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------
@notifications_bp.route("/register", methods=["POST"])
@require_auth
@rate_limit(max_calls=20, window_seconds=60)
def register_token():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    platform = (data.get("platform") or "unknown").strip()[:32]
    if not token or len(token) > 4096:
        return jsonify({"error": "token is required (max 4096 chars)"}), 400
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO device_tokens (token, user_id, platform) "
            "VALUES (?, ?, ?)",
            (token, g.user_id, platform),
        )
    return jsonify({"registered": True, "platform": platform}), 201


@notifications_bp.route("/unregister", methods=["POST"])
@require_auth
def unregister_token():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM device_tokens WHERE token = ? AND user_id = ?",
            (token, g.user_id),
        )
    return jsonify({"removed": cur.rowcount})


@notifications_bp.route("/tokens", methods=["GET"])
@require_auth
def list_tokens():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT platform, substr(token, 1, 12) AS prefix, created_at "
            "FROM device_tokens WHERE user_id = ? ORDER BY created_at DESC",
            (g.user_id,),
        ).fetchall()
    return jsonify({"tokens": [dict(r) for r in rows], "count": len(rows)})


@notifications_bp.route("/test", methods=["POST"])
@require_auth
@rate_limit(max_calls=5, window_seconds=60)
def test_notification():
    project_id, token = _credentials()
    configured = bool(project_id and token)
    sent = send_push(
        g.user_id,
        "Arithmetic Super App",
        "Test notification — push is working!",
        {"kind": "test"},
    )
    return jsonify({"sent": sent, "configured": configured})


# ---------------------------------------------------------------------
# Helpers for other blueprints
# ---------------------------------------------------------------------
def notify_room_invite(invitee_user_id: int, room: str, inviter: str) -> None:
    send_push(
        invitee_user_id,
        f"Invite to {room}",
        f"{inviter} invited you to join the room.",
        {"kind": "room_invite", "room": room},
    )


def notify_mention(user_id: int, room: str, sender: str, preview: str) -> None:
    send_push(
        user_id,
        f"New message in {room}",
        f"{sender}: {preview[:80]}",
        {"kind": "mention", "room": room},
    )
