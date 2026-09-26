"""Background retention jobs (Phase 24).

Purges old rows based on configurable TTLs. Exposed via admin endpoints
so the dashboard can show last-run stats. No scheduler required — a
thread is started on app boot when RETENTION_ENABLED=1.
"""
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from .database import get_db
from .logging_config import get_logger

log = get_logger("web.jobs")

# In-memory last-run stats (not persisted; reset on restart)
STATS = {
    "last_run": None,
    "last_duration_ms": None,
    "last_deleted": {},
    "total_runs": 0,
}

_thread = None
_stop = threading.Event()


def _ttl(name: str, default_days: int) -> int:
    try:
        return int(os.environ.get(name, str(default_days)))
    except ValueError:
        return default_days


def run_retention() -> dict:
    """Run all retention jobs. Returns a dict of deleted counts."""
    now = datetime.now(timezone.utc)
    deleted = {}

    # 1. Old calculations
    days = _ttl("RETENTION_CALC_DAYS", 0)  # 0 = keep forever
    if days > 0:
        cutoff = (now - timedelta(days=days)).isoformat()
        with get_db() as conn:
            cur = conn.execute("DELETE FROM calculations WHERE created_at < ?", (cutoff,))
            deleted["calculations"] = cur.rowcount

    # 2. Old chat messages
    days = _ttl("RETENTION_CHAT_DAYS", 0)
    if days > 0:
        cutoff = (now - timedelta(days=days)).isoformat()
        with get_db() as conn:
            cur = conn.execute("DELETE FROM chat_messages WHERE created_at < ?", (cutoff,))
            deleted["chat_messages"] = cur.rowcount

    # 3. Old audit entries
    days = _ttl("RETENTION_AUDIT_DAYS", 0)
    if days > 0:
        cutoff = (now - timedelta(days=days)).isoformat()
        with get_db() as conn:
            cur = conn.execute("DELETE FROM audit_log WHERE created_at < ?", (cutoff,))
            deleted["audit_log"] = cur.rowcount

    # 4. Expired room invites
    now_iso = now.isoformat()
    with get_db() as conn:
        cur = conn.execute("DELETE FROM room_invites WHERE expires_at < ?", (now_iso,))
        if cur.rowcount:
            deleted["room_invites"] = cur.rowcount

    # 5. Old device tokens (FCM tokens expire after ~270 days of inactivity)
    days = _ttl("RETENTION_DEVICE_DAYS", 270)
    if days > 0:
        cutoff = (now - timedelta(days=days)).isoformat()
        with get_db() as conn:
            cur = conn.execute("DELETE FROM device_tokens WHERE created_at < ?", (cutoff,))
            if cur.rowcount:
                deleted["device_tokens"] = cur.rowcount

    # Update stats
    STATS["last_run"] = now.isoformat(timespec="seconds") + "Z"
    STATS["last_deleted"] = deleted
    STATS["total_runs"] += 1

    return deleted


def _loop(interval_seconds: int) -> None:
    log.info("retention loop starting (interval=%ds)", interval_seconds)
    while not _stop.is_set():
        try:
            t0 = time.time()
            result = run_retention()
            STATS["last_duration_ms"] = round((time.time() - t0) * 1000, 2)
            if any(v > 0 for v in result.values()):
                log.info("retention purged: %s", result)
        except Exception as e:
            log.error("retention run failed: %s", e, exc_info=True)
        _stop.wait(interval_seconds)
    log.info("retention loop stopped")


def start_if_enabled() -> bool:
    """Start the background retention thread if RETENTION_ENABLED=1."""
    global _thread
    if os.environ.get("RETENTION_ENABLED", "").lower() not in ("1", "true", "yes", "on"):
        return False
    if _thread and _thread.is_alive():
        return True

    try:
        hours = int(os.environ.get("RETENTION_INTERVAL_HOURS", "24"))
    except ValueError:
        hours = 24
    interval = max(60, hours * 3600)

    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(interval,), daemon=True)
    _thread.start()
    return True


def stop() -> None:
    """Signal the retention thread to stop (for tests)."""
    _stop.set()


def snapshot() -> dict:
    """Return a copy of the current stats (safe to call from admin)."""
    return {
        "last_run": STATS["last_run"],
        "last_duration_ms": STATS["last_duration_ms"],
        "last_deleted": dict(STATS["last_deleted"]),
        "total_runs": STATS["total_runs"],
        "ttls": {
            "calculations_days": _ttl("RETENTION_CALC_DAYS", 0),
            "chat_days": _ttl("RETENTION_CHAT_DAYS", 0),
            "audit_days": _ttl("RETENTION_AUDIT_DAYS", 0),
            "device_days": _ttl("RETENTION_DEVICE_DAYS", 270),
        },
        "enabled": os.environ.get("RETENTION_ENABLED", "").lower() in ("1", "true", "yes", "on"),
    }
