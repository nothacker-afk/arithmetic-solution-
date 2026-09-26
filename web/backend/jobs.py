"""Background retention jobs (Phase 24 + Phase 39).

Purges old rows based on configurable TTLs, plus expired disappearing
messages. Runs in a background thread when RETENTION_ENABLED=1.
"""
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from .database import get_db
from .logging_config import get_logger

log = get_logger("web.jobs")

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
    """Run every retention job. Returns dict of deletion counts."""
    now = datetime.now(timezone.utc)
    deleted = {}

    # 1. Expired disappearing chat messages (Phase 39)
    now_iso = now.isoformat(timespec="seconds")
    try:
        with get_db() as conn:
            cur = conn.execute(
                "DELETE FROM chat_messages "
                "WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now_iso,),
            )
            if cur.rowcount:
                deleted["expired_chat"] = cur.rowcount

            cur = conn.execute(
                "DELETE FROM dm_messages "
                "WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now_iso,),
            )
            if cur.rowcount:
                deleted["expired_dm"] = cur.rowcount
    except Exception as e:
        log.warning("expired-message purge failed: %s", e)

    # 2. Old calculations
    days = _ttl("RETENTION_CALC_DAYS", 0)
    if days > 0:
        cutoff = (now - timedelta(days=days)).isoformat()
        with get_db() as conn:
            cur = conn.execute("DELETE FROM calculations WHERE created_at < ?", (cutoff,))
            if cur.rowcount:
                deleted["calculations"] = cur.rowcount

    # 3. Old chat messages
    days = _ttl("RETENTION_CHAT_DAYS", 0)
    if days > 0:
        cutoff = (now - timedelta(days=days)).isoformat()
        with get_db() as conn:
            cur = conn.execute("DELETE FROM chat_messages WHERE created_at < ?", (cutoff,))
            if cur.rowcount:
                deleted["chat_messages"] = cur.rowcount

    # 4. Old audit entries
    days = _ttl("RETENTION_AUDIT_DAYS", 0)
    if days > 0:
        cutoff = (now - timedelta(days=days)).isoformat()
        with get_db() as conn:
            cur = conn.execute("DELETE FROM audit_log WHERE created_at < ?", (cutoff,))
            if cur.rowcount:
                deleted["audit_log"] = cur.rowcount

    # 5. Expired room invites
    with get_db() as conn:
        cur = conn.execute("DELETE FROM room_invites WHERE expires_at < ?",
                           (now.isoformat(),))
        if cur.rowcount:
            deleted["room_invites"] = cur.rowcount

    # 6. Old device tokens
    days = _ttl("RETENTION_DEVICE_DAYS", 270)
    if days > 0:
        cutoff = (now - timedelta(days=days)).isoformat()
        with get_db() as conn:
            cur = conn.execute("DELETE FROM device_tokens WHERE created_at < ?", (cutoff,))
            if cur.rowcount:
                deleted["device_tokens"] = cur.rowcount

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
    _stop.set()


def snapshot() -> dict:
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
