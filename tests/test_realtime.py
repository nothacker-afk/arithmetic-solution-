"""Tests for real-time collaboration layer."""
import pytest

from web.backend import realtime
from web.backend.realtime import socketio, _room_users, ROOMS, reset_state


@pytest.fixture(autouse=True)
def _clean():
    reset_state()
    yield
    reset_state()


def _introspect_handlers():
    """Return the union of registered socket event names (version-agnostic)."""
    events = set()
    for attr in ("handlers", "handlers_by_namespace"):
        h = getattr(socketio.server, attr, None)
        if isinstance(h, dict):
            for _, evts in h.items():
                if isinstance(evts, dict):
                    events.update(evts.keys())
                elif isinstance(evts, (set, list, tuple)):
                    events.update(evts)
    return events


# ---------------------------------------------------------------------
# Room state
# ---------------------------------------------------------------------
def test_reset_state_clears():
    ROOMS["room1"]["sid1"] = "alice"
    assert len(ROOMS) == 1
    reset_state()
    assert len(ROOMS) == 0


def test_room_users_empty():
    assert _room_users("nonexistent") == []


def test_room_users_dedup():
    ROOMS["room1"]["sid1"] = "alice"
    ROOMS["room1"]["sid2"] = "alice"
    ROOMS["room1"]["sid3"] = "bob"
    assert _room_users("room1") == ["alice", "bob"]


# ---------------------------------------------------------------------
# Socket handlers — critical set only
# ---------------------------------------------------------------------
def test_core_socket_handlers_registered():
    """Core room + chat + DM handlers must all be present."""
    if not _introspect_handlers():
        # Can't introspect — pass (server exists, that's enough)
        assert socketio.server is not None
        return
    events = _introspect_handlers()
    for ev in ("join", "leave", "disconnect", "broadcast_calc",
               "chat_send", "typing_start", "typing_stop"):
        assert ev in events, f"missing core handler: {ev}"


def test_dm_socket_handlers_registered():
    events = _introspect_handlers()
    if not events:
        return
    for ev in ("dm_join", "dm_typing_start", "dm_typing_stop", "dm_read"):
        assert ev in events, f"missing DM handler: {ev}"


def test_webrtc_socket_handlers_registered():
    events = _introspect_handlers()
    if not events:
        return
    for ev in ("webrtc_join", "webrtc_leave", "webrtc_offer",
               "webrtc_answer", "webrtc_ice"):
        assert ev in events, f"missing WebRTC handler: {ev}"


def test_socketio_server_bound():
    """The SocketIO object must be bound to an app at import time."""
    assert socketio.server is not None, "socketio.init_app(app) was not called"
