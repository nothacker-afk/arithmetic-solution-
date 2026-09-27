"""Email digests (Phase 75).

Sends periodic summaries to users via SMTP. Uses only stdlib.

Env vars:
    SMTP_HOST       (required to enable)
    SMTP_PORT       (default 587)
    SMTP_USERNAME
    SMTP_PASSWORD
    SMTP_FROM       (default noreply@localhost)
    SMTP_USE_TLS    (default true)

Endpoints:
    GET    /api/digest/subscription
    PUT    /api/digest/subscription       {frequency, enabled}
    POST   /api/digest/test               send one now
"""
import os
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .logging_config import get_logger
from .datetime_utils import parse_iso

log = get_logger("web.digests")

digest_bp = Blueprint("digest", __name__, url_prefix="/api/digest")

VALID_FREQUENCIES = {"daily", "weekly"}


def _smtp_config() -> dict:
    return {
        "host": os.environ.get("SMTP_HOST"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "username": os.environ.get("SMTP_USERNAME"),
        "password": os.environ.get("SMTP_PASSWORD"),
        "from_addr": os.environ.get("SMTP_FROM", "noreply@localhost"),
        "use_tls": os.environ.get("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes"),
    }


def smtp_available() -> bool:
    return bool(os.environ.get("SMTP_HOST"))


# ---------------------------------------------------------------------
# Composing digests
# ---------------------------------------------------------------------
def _compose(user_id: int) -> dict:
    """Gather recent activity for a user. Returns a dict."""
    since = (datetime.now(timezone.utc) - timedelta(days=1 if False else 7)).isoformat()

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username, email FROM users WHERE id = ?", (user_id,),
        ).fetchone()
        if not user:
            return {}

        calcs = conn.execute("""
            SELECT COUNT(*) AS n FROM calculations
            WHERE user_id = ? AND created_at >= ?
        """, (user_id, since)).fetchone()["n"]

        rooms = conn.execute("""
            SELECT r.name,
                   (SELECT COUNT(*) FROM chat_messages
                    WHERE room_id = r.name AND created_at >= ?) AS new_messages
            FROM rooms r
            JOIN room_members m ON m.room_name = r.name
            WHERE m.user_id = ?
            ORDER BY new_messages DESC
            LIMIT 10
        """, (since, user_id)).fetchall()

        events = conn.execute("""
            SELECT title, starts_at, room_id FROM room_events
            WHERE starts_at >= ? ORDER BY starts_at LIMIT 10
        """, (datetime.now(timezone.utc).isoformat(),)).fetchall()

    return {
        "username": user["username"],
        "email": user["email"],
        "calcs": calcs,
        "rooms": [dict(r) for r in rooms],
        "events": [dict(e) for e in events],
    }


def _render_html(summary: dict) -> str:
    rooms_html = "".join(
        f"<li><strong>{r['name']}</strong>: {r['new_messages']} new messages</li>"
        for r in summary["rooms"] if r["new_messages"] > 0
    ) or "<li class='muted'>(no new activity)</li>"

    events_html = "".join(
        f"<li><strong>{e['title']}</strong> — {e['starts_at']} in {e['room_id']}</li>"
        for e in summary["events"]
    ) or "<li class='muted'>(no upcoming events)</li>"

    return f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:20px auto;">
<h1>Weekly summary for {summary['username']}</h1>
<p>You ran <strong>{summary['calcs']}</strong> calculations this week.</p>

<h2>Room activity</h2>
<ul>{rooms_html}</ul>

<h2>Upcoming events</h2>
<ul>{events_html}</ul>

<p style="color:#64748b;font-size:12px;">
Arithmetic Super App · <a href="/api/digest/subscription">manage subscription</a>
</p>
</body></html>"""


def send_digest(user_id: int, subject: str = None) -> tuple[bool, str]:
    """Send a digest email. Returns (success, message)."""
    cfg = _smtp_config()
    if not cfg["host"]:
        return False, "SMTP not configured"

    summary = _compose(user_id)
    if not summary:
        return False, "User not found"

    subject = subject or f"Your weekly summary — {summary['username']}"
    html = _render_html(summary)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = summary["email"]
    msg.attach(MIMEText(html, "html"))

    try:
        if cfg["use_tls"]:
            context = ssl.create_default_context()
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as s:
                s.starttls(context=context)
                if cfg["username"]:
                    s.login(cfg["username"], cfg["password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as s:
                if cfg["username"]:
                    s.login(cfg["username"], cfg["password"])
                s.send_message(msg)
    except Exception as e:
        log.warning("digest send failed for %s: %s", user_id, e)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO digest_log (user_id, status, details) VALUES (?, 'failed', ?)",
                (user_id, str(e)[:200]),
            )
        return False, str(e)

    with get_db() as conn:
        conn.execute("INSERT INTO digest_log (user_id, status) VALUES (?, 'sent')", (user_id,))
        conn.execute(
            "UPDATE digest_subscriptions SET last_sent_at = CURRENT_TIMESTAMP "
            "WHERE user_id = ?", (user_id,),
        )

    return True, "sent"


# ---------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------
@digest_bp.route("/subscription", methods=["GET"])
@require_auth
def get_subscription():
    with get_db() as conn:
        row = conn.execute(
            "SELECT frequency, enabled, last_sent_at FROM digest_subscriptions "
            "WHERE user_id = ?", (g.user_id,),
        ).fetchone()
    if not row:
        return jsonify({"frequency": "weekly", "enabled": False,
                        "last_sent_at": None})
    return jsonify({
        "frequency": row["frequency"],
        "enabled": bool(row["enabled"]),
        "last_sent_at": row["last_sent_at"],
    })


@digest_bp.route("/subscription", methods=["PUT"])
@require_auth
def set_subscription():
    data = request.get_json(silent=True) or {}
    frequency = (data.get("frequency") or "weekly").lower()
    enabled = 1 if data.get("enabled", True) else 0

    if frequency not in VALID_FREQUENCIES:
        return jsonify({"error": f"frequency must be one of {sorted(VALID_FREQUENCIES)}"}), 400

    with get_db() as conn:
        conn.execute("""
            INSERT INTO digest_subscriptions (user_id, frequency, enabled, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                frequency = excluded.frequency,
                enabled = excluded.enabled,
                updated_at = CURRENT_TIMESTAMP
        """, (g.user_id, frequency, enabled))

    return jsonify({"frequency": frequency, "enabled": bool(enabled)})


@digest_bp.route("/test", methods=["POST"])
@require_auth
@rate_limit(max_calls=3, window_seconds=300)
def send_test():
    if not smtp_available():
        return jsonify({"error": "SMTP not configured on this server"}), 503
    ok, msg = send_digest(g.user_id, subject="Test digest")
    return jsonify({"sent": ok, "message": msg}), (200 if ok else 500)


# ---------------------------------------------------------------------
# Background tick
# ---------------------------------------------------------------------
def tick(now=None) -> int:
    """Send digests for users whose frequency window has elapsed."""
    if now is None:
        now = datetime.now(timezone.utc)
    if not smtp_available():
        return 0

    sent = 0
    with get_db() as conn:
        rows = conn.execute("""
            SELECT user_id, frequency, last_sent_at
            FROM digest_subscriptions WHERE enabled = 1
        """).fetchall()

    for r in rows:
        freq = r["frequency"]
        hours = 24 if freq == "daily" else 24 * 7
        last = r["last_sent_at"]
        if last:
            try:
                last_dt = parse_iso(last.replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if (now - last_dt).total_seconds() < hours * 3600:
                    continue
            except Exception:
                pass
        ok, _ = send_digest(r["user_id"])
        if ok:
            sent += 1

    return sent
