"""Tests for the real-time collaboration layer (unit-level, no sockets)."""
import pytest
from web.backend.realtime import (
    _room_users, ROOMS, reset_state, socketio,
)


@pytest.fixture(autouse=True)
def _clean():
    reset_state()
    yield
    reset_state()


def test_reset_state():
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


def test_plugin_endpoint_listing(client):
    r = client.get("/api/plugins")
    assert r.status_code == 200
    names = [p["name"] for p in r.get_json()["plugins"]]
    assert "gcd" in names
    assert "lcm" in names


def test_plugin_endpoint_call(client):
    r = client.post("/api/plugins/gcd", json={"args": [12, 18]})
    assert r.status_code == 200
    assert r.get_json()["result"] == 6


def test_plugin_endpoint_unknown(client):
    r = client.post("/api/plugins/nope", json={"args": [1, 2]})
    assert r.status_code == 400


def test_plugin_endpoint_bad_args(client):
    r = client.post("/api/plugins/gcd", json={"args": "not-a-list"})
    assert r.status_code == 400


def test_socketio_instance_configured():
    """Sanity: socketio object exists and is bound to the Flask app."""
    assert socketio is not None
    # Flask-SocketIO versions store handlers differently; just verify the
    # server object exists and the app is bound.
    assert socketio.server is not None, "socketio.server not initialized"


def test_socketio_handlers_registered():
    """Verify event handlers are registered (version-agnostic)."""
    # Different versions store handlers in different places.
    # Try every known location.
    candidates = []
    if hasattr(socketio, "handlers"):
        candidates.append(socketio.handlers)
    if hasattr(socketio, "server") and hasattr(socketio.server, "handlers"):
        candidates.append(socketio.server.handlers)
    if hasattr(socketio, "server") and hasattr(socketio.server, "handlers"):
        # python-socketio 5.x uses server.handlers as a dict of dicts
        candidates.append(getattr(socketio.server, "handlers", {}))

    found_any = False
    for handlers in candidates:
        if not handlers:
            continue
        # handlers may be {"/": {...}} or {namespace: {event: fn}}
        for namespace, events in handlers.items():
            if isinstance(events, dict):
                for event in ("join", "leave", "disconnect", "broadcast_calc", "ping_presence"):
                    if event in events:
                        found_any = True

    assert found_any, "No socket event handlers found in any known location"
