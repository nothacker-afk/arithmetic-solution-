"""Outbound webhooks (Phase 87).

Owners configure URLs; the server POSTs signed JSON when events fire.
Signing: HMAC-SHA256(body, secret), header `X-Webhook-Signature: sha256=...`.

Endpoints:
    GET    /api/webhooks
    POST   /api/webhooks                  {url, events[], description?}
    PATCH  /api/webhooks/<id>             {url?, events?, enabled?, description?}
    DELETE /api/webhooks/<id>
    GET    /api/webhooks/<id>/deliveries
    POST   /api/webhooks/<id>/test        send a test event

Supported events:
    message.created       any new chat / dm / group message
    dm.created            a new DM thread was started
    user.registered       a new user account
    room.published        a room was published to Discover
    webhook.test          synthetic test event
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
import uuid

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event
from .logging_config import get_logger

log = get_logger("web.webhooks")

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")

WEBHOOK_ID_RE = __import__("re").compile(r"^[0-9a-f]{32}$")
VALID_EVENTS = {
    "message.created",
    "dm.created",
    "user.registered",
    "room.published",
    "webhook.test",
}
MAX_URL = 500
TIMEOUT = 8


# ---------------------------------------------------------------------
# Signing + delivery
# ---------------------------------------------------------------------
def _sign(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def _deliver(webhook_id: str, url: str, secret: str, event: str, payload: dict) -> None:
    """Perform the HTTP POST. Best-effort; logs to webhook_deliveries."""
    body = json.dumps({
        "event": event,
        "delivered_at": time.time(),
        "payload": payload,
    }).encode("utf-8")

    signature = _sign(body, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": event,
        "User-Agent": "ArithmeticSuperApp/1.0",
    }

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    t0 = time.time()
    status_code = None
    error = None
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status_code = resp.status
    except urllib.error.HTTPError as e:
        status_code = e.code
        error = f"HTTP {e.code}"
    except Exception as e:
        error = str(e)[:200]
    duration_ms = int((time.time() - t0) * 1000)

    # Log
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO webhook_deliveries
                (webhook_id, event, status_code, error, duration_ms)
                VALUES (?, ?, ?, ?, ?)
            """, (webhook_id, event, status_code, error, duration_ms))
            conn.execute(
                "UPDATE webhooks SET last_delivery_at = CURRENT_TIMESTAMP, "
                "  last_status_code = ?, "
                "  failure_count = CASE WHEN ? IS NULL THEN 0 ELSE failure_count + 1 END "
                "WHERE id = ?",
                (status_code, error, webhook_id),
            )
    except Exception as e:
        log.warning("webhook delivery logging failed: %s", e)

    if error:
        log.info("webhook %s → %s: %s", webhook_id, url, error)
    else:
        log.info("webhook %s → %s: %s (%dms)", webhook_id, url, status_code, duration_ms)


def dispatch(event: str, payload: dict, owner_id: int = None) -> int:
    """Fire all enabled webhooks that subscribe to `event`.

    If `owner_id` is given, only dispatches to that user's webhooks
    (used for user-scoped events like user.registered).
    """
    if event not in VALID_EVENTS:
        return 0

    with get_db() as conn:
        if owner_id is not None:
            rows = conn.execute(
                "SELECT id, url, secret, events FROM webhooks "
                "WHERE enabled = 1 AND user_id = ?", (owner_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, url, secret, events FROM webhooks WHERE enabled = 1",
            ).fetchall()

    fired = 0
    for r in rows:
        events = set((r["events"] or "").split(","))
        if event not in events:
            continue
        # Fire in a daemon thread so we never block the request path
        t = threading.Thread(
            target=_deliver,
            args=(r["id"], r["url"], r["secret"], event, payload),
            daemon=True,
        )
        t.start()
        fired += 1

    return fired


# ---------------------------------------------------------------------
# Management endpoints
# ---------------------------------------------------------------------
@webhooks_bp.route("", methods=["GET"])
@require_auth
def list_webhooks():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, url, events, description, enabled,
                   created_at, last_delivery_at, last_status_code, failure_count
            FROM webhooks WHERE user_id = ?
            ORDER BY created_at DESC
        """, (g.user_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d.pop("secret", None)  # never return secret after creation
        out.append(d)
    return jsonify({"webhooks": out})


@webhooks_bp.route("", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def create_webhook():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    events = data.get("events") or []
    description = (data.get("description") or "").strip()[:200] or None

    if not url or len(url) > MAX_URL:
        return jsonify({"error": "url required (max 500 chars)"}), 400
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"error": "url must start with http:// or https://"}), 400
    if not isinstance(events, list) or not events:
        return jsonify({"error": "events must be a non-empty list"}), 400
    invalid = set(events) - VALID_EVENTS
    if invalid:
        return jsonify({"error": f"unknown events: {sorted(invalid)}"}), 400

    webhook_id = uuid.uuid4().hex
    secret = secrets.token_urlsafe(32)

    with get_db() as conn:
        conn.execute("""
            INSERT INTO webhooks (id, user_id, url, secret, events, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (webhook_id, g.user_id, url, secret,
              ",".join(sorted(set(events))), description))

    log_event("webhook.create", actor_id=g.user_id, resource="webhook",
              resource_id=webhook_id, details={"url": url, "events": events})

    return jsonify({
        "id": webhook_id,
        "url": url,
        "events": sorted(set(events)),
        "description": description,
        "secret": secret,  # shown ONCE
    }), 201


@webhooks_bp.route("/<webhook_id>", methods=["PATCH"])
@require_auth
def update_webhook(webhook_id):
    if not WEBHOOK_ID_RE.match(webhook_id):
        return jsonify({"error": "Invalid id"}), 400
    data = request.get_json(silent=True) or {}

    sets, params = [], []
    if "url" in data:
        url = (data.get("url") or "").strip()
        if not url or len(url) > MAX_URL or not (url.startswith("http") or url.startswith("https")):
            return jsonify({"error": "invalid url"}), 400
        sets.append("url = ?"); params.append(url)
    if "events" in data:
        events = data.get("events") or []
        if not isinstance(events, list) or not events:
            return jsonify({"error": "events required"}), 400
        invalid = set(events) - VALID_EVENTS
        if invalid:
            return jsonify({"error": f"unknown events: {sorted(invalid)}"}), 400
        sets.append("events = ?"); params.append(",".join(sorted(set(events))))
    if "enabled" in data:
        sets.append("enabled = ?"); params.append(1 if data["enabled"] else 0)
    if "description" in data:
        sets.append("description = ?"); params.append((data["description"] or "").strip()[:200] or None)

    if not sets:
        return jsonify({"error": "nothing to update"}), 400

    params.extend([webhook_id, g.user_id])
    with get_db() as conn:
        cur = conn.execute(
            f"UPDATE webhooks SET {', '.join(sets)} WHERE id = ? AND user_id = ?",
            tuple(params),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not found"}), 404
        row = conn.execute(
            "SELECT id, url, events, description, enabled FROM webhooks WHERE id = ?",
            (webhook_id,),
        ).fetchone()
    return jsonify(dict(row))


@webhooks_bp.route("/<webhook_id>", methods=["DELETE"])
@require_auth
def delete_webhook(webhook_id):
    if not WEBHOOK_ID_RE.match(webhook_id):
        return jsonify({"error": "Invalid id"}), 400
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM webhooks WHERE id = ? AND user_id = ?",
            (webhook_id, g.user_id),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "Not found"}), 404
        conn.execute("DELETE FROM webhook_deliveries WHERE webhook_id = ?", (webhook_id,))
    log_event("webhook.delete", actor_id=g.user_id, resource="webhook", resource_id=webhook_id)
    return jsonify({"deleted": webhook_id})


@webhooks_bp.route("/<webhook_id>/deliveries", methods=["GET"])
@require_auth
def list_deliveries(webhook_id):
    if not WEBHOOK_ID_RE.match(webhook_id):
        return jsonify({"error": "Invalid id"}), 400
    with get_db() as conn:
        # ownership check
        owner = conn.execute(
            "SELECT user_id FROM webhooks WHERE id = ?", (webhook_id,),
        ).fetchone()
        if not owner or owner["user_id"] != g.user_id:
            return jsonify({"error": "Not found"}), 404

        rows = conn.execute("""
            SELECT id, event, status_code, error, duration_ms, attempt, created_at
            FROM webhook_deliveries
            WHERE webhook_id = ?
            ORDER BY created_at DESC LIMIT 100
        """, (webhook_id,)).fetchall()
    return jsonify({"deliveries": [dict(r) for r in rows]})


@webhooks_bp.route("/<webhook_id>/test", methods=["POST"])
@require_auth
@rate_limit(max_calls=5, window_seconds=60)
def test_webhook(webhook_id):
    if not WEBHOOK_ID_RE.match(webhook_id):
        return jsonify({"error": "Invalid id"}), 400
    with get_db() as conn:
        row = conn.execute(
            "SELECT url, secret FROM webhooks WHERE id = ? AND user_id = ?",
            (webhook_id, g.user_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404

    # Deliver synchronously for the test endpoint so the user sees the result
    t = threading.Thread(
        target=_deliver,
        args=(webhook_id, row["url"], row["secret"], "webhook.test",
              {"message": "Test delivery from Arithmetic Super App"}),
        daemon=True,
    )
    t.start()
    t.join(timeout=TIMEOUT + 2)

    with get_db() as conn:
        latest = conn.execute("""
            SELECT status_code, error, duration_ms
            FROM webhook_deliveries WHERE webhook_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (webhook_id,)).fetchone()

    if not latest:
        return jsonify({"sent": False, "error": "no delivery recorded"}), 500
    return jsonify({
        "sent": latest["status_code"] is not None and 200 <= (latest["status_code"] or 0) < 300,
        "status_code": latest["status_code"],
        "error": latest["error"],
        "duration_ms": latest["duration_ms"],
    })
