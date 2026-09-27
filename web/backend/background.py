"""Unified background scheduler (Phases 46, 73, 75).

Runs a single daemon thread that periodically calls:
    - scheduled.dispatch_due()  (Phase 46)
    - event_reminders.tick()    (Phase 73)
    - digests.tick()            (Phase 75)
    - jobs.run_retention()      (already started elsewhere)

Started from main.py once at import. Configurable interval via
BACKGROUND_INTERVAL_SECONDS (default 30).
"""
import os
import threading
import time

from .logging_config import get_logger

log = get_logger("web.background")

_thread = None
_stop = threading.Event()
_LAST_STATS = {"runs": 0, "last_started": None, "last_duration_ms": None}


def _tick() -> dict:
    result = {}
    try:
        from .scheduled import dispatch_due
        n = dispatch_due()
        if n:
            result["scheduled_dispatched"] = n
    except Exception as e:
        log.warning("scheduled dispatch failed: %s", e)

    try:
        from .event_reminders import tick as reminders_tick
        n = reminders_tick()
        if n:
            result["reminders_sent"] = n
    except Exception as e:
        log.warning("reminders tick failed: %s", e)

    try:
        from .digests import tick as digests_tick
        n = digests_tick()
        if n:
            result["digests_sent"] = n
    except Exception as e:
        log.warning("digests tick failed: %s", e)

    return result


def _loop(interval: int):
    log.info("background loop started (interval=%ds)", interval)
    while not _stop.is_set():
        t0 = time.time()
        try:
            stats = _tick()
            if stats:
                log.info("background tick: %s", stats)
        except Exception as e:
            log.error("background tick error: %s", e, exc_info=True)
        finally:
            _LAST_STATS["runs"] += 1
            _LAST_STATS["last_started"] = time.time()
            _LAST_STATS["last_duration_ms"] = round((time.time() - t0) * 1000, 2)
        _stop.wait(interval)
    log.info("background loop stopped")


def start() -> bool:
    global _thread
    if _thread and _thread.is_alive():
        return True
    try:
        interval = int(os.environ.get("BACKGROUND_INTERVAL_SECONDS", "30"))
    except ValueError:
        interval = 30
    interval = max(5, interval)
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(interval,), daemon=True)
    _thread.start()
    return True


def stop():
    _stop.set()


def stats() -> dict:
    return dict(_LAST_STATS)
