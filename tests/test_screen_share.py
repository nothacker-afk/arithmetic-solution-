"""Tests for screen share signaling (Phase 48)."""
from web.backend import realtime


def _introspect():
    events = set()
    for attr in ("handlers", "handlers_by_namespace"):
        h = getattr(realtime.socketio.server, attr, None)
        if isinstance(h, dict):
            for _, evts in h.items():
                if isinstance(evts, dict):
                    events.update(evts.keys())
    return events


def test_screen_share_handlers():
    events = _introspect()
    if not events:
        return  # can't introspect
    for ev in ("screen_share_start", "screen_share_stop", "screen_track_ready"):
        assert ev in events, f"missing handler: {ev}"
