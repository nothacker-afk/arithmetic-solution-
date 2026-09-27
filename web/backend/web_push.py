"""Web Push notifications (Phase 79).

VAPID-signed browser push. Requires the `pywebpush` package:
    pip install pywebpush

Env vars:
    VAPID_PUBLIC_KEY       (base64url-encoded)
    VAPID_PRIVATE_KEY      (base64url-encoded)
    VAPID_SUBJECT          mailto:you@example.com (required by spec)

Endpoints:
    GET    /api/push/vapid-public-key        frontend fetches to subscribe
    POST   /api/push/subscribe               {endpoint, keys: {p256dh, auth}}
    DELETE /api/push/subscribe               {endpoint}
    GET    /api/push/subscriptions           list my subscriptions
    POST   /api/push/test                    send a test push to all my devices
"""
import base64
import json
import os

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .logging_config import get_logger

log = get_logger("web.webpush")

wp_bp = Blueprint("web_push", __name__, url_prefix="/api/push")


def _pywebpush_available() -> bool:
    try:
        import pywebpush  # noqa: F401
        return True
    except ImportError:
        return False


def _vapid_configured() -> bool:
    return bool(os.environ.get("VAPID_PUBLIC_KEY") and
                os.environ.get("VAPID_PRIVATE_KEY"))


def is_enabled() -> bool:
    return _pywebpush_available() and _vapid_configured()


@wp_bp.route("/vapid-public-key", methods=["GET"])
def vapid_public_key():
    """Public key for the browser to use when subscribing."""
    if not _vapid_configured():
        return jsonify({"error": "Web push not configured on this server"}), 503
    return jsonify({
        "public_key": os.environ["VAPID_PUBLIC_KEY"],
        "subject": os.environ.get("VAPID_SUBJECT", "mailto:noreply@localhost"),
    })


@wp_bp.route("/subscribe", methods=["POST"])
@require_auth
@rate_limit(max_calls=20, window_seconds=60)
def subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = (data.get("endpoint") or "").strip()
    keys = data.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "endpoint + keys.p256dh + keys.auth required"}), 400
    if len(endpoint) > 1000:
        return jsonify({"error": "endpoint too long"}), 400

    ua = (request.headers.get("User-Agent") or "")[:200]

    with get_db() as conn:
        conn.execute("""
            INSERT INTO web_push_subscriptions
            (user_id, endpoint, p256dh, auth, user_agent)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET
                user_id = excluded.user_id,
                p256dh = excluded.p256dh,
                auth = excluded.auth,
                user_agent = excluded.user_agent,
                last_used_at = CURRENT_TIMESTAMP
        """, (g.user_id, endpoint, p256dh, auth, ua))

    return jsonify({"subscribed": True}), 201


@wp_bp.route("/subscribe", methods=["DELETE"])
@require_auth
def unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = (data.get("endpoint") or "").strip()
    if not endpoint:
        return jsonify({"error": "endpoint required"}), 400
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM web_push_subscriptions "
            "WHERE user_id = ? AND endpoint = ?",
            (g.user_id, endpoint),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Subscription not found"}), 404
    return jsonify({"removed": True})


@wp_bp.route("/subscriptions", methods=["GET"])
@require_auth
def list_subscriptions():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, endpoint, user_agent, created_at, last_used_at
            FROM web_push_subscriptions
            WHERE user_id = ?
            ORDER BY last_used_at DESC
        """, (g.user_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        # Truncate the endpoint — never leak the full URL
        ep = d["endpoint"]
        d["endpoint_prefix"] = ep[:40] + "…" if len(ep) > 40 else ep
        d.pop("endpoint")
        out.append(d)
    return jsonify({"subscriptions": out, "count": len(out)})


# ---------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------
def send_to_user(user_id: int, title: str, body: str, data: dict = None) -> int:
    """Send a push to every subscription for a user. Returns delivered count."""
    if not is_enabled():
        log.info("push (dry-run) user=%s title=%r", user_id, title)
        return 0

    from pywebpush import webpush, WebPushException

    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, endpoint, p256dh, auth FROM web_push_subscriptions "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchall()

    payload = json.dumps({
        "title": title,
        "body": body,
        "data": data or {},
    })
    vapid = {
        "vapid_private_key": os.environ["VAPID_PRIVATE_KEY"],
        "vapid_claims": {
            "sub": os.environ.get("VAPID_SUBJECT", "mailto:noreply@localhost"),
        },
    }
    delivered = 0
    stale = []

    for r in rows:
        sub = {
            "endpoint": r["endpoint"],
            "keys": {"p256dh": r["p256dh"], "auth": r["auth"]},
        }
        try:
            webpush(subscription_info=sub, data=payload, **vapid)
            delivered += 1
        except WebPushException as e:
            # 404/410 = subscription no longer valid
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                stale.append(r["id"])
            else:
                log.warning("web push failed: %s", e)
        except Exception as e:
            log.warning("web push error: %s", e)

    if stale:
        with get_db() as conn:
            for sid in stale:
                conn.execute("DELETE FROM web_push_subscriptions WHERE id = ?", (sid,))
        log.info("pruned %d stale web push subscriptions", len(stale))

    return delivered


@wp_bp.route("/test", methods=["POST"])
@require_auth
@rate_limit(max_calls=5, window_seconds=60)
def test_push():
    if not _vapid_configured():
        return jsonify({"error": "Web push not configured on this server"}), 503
    delivered = send_to_user(
        g.user_id,
        "Test notification",
        "Web push is working!",
        {"kind": "test"},
    )
    return jsonify({
        "sent": delivered,
        "configured": True,
        "pywebpush_installed": _pywebpush_available(),
    })
