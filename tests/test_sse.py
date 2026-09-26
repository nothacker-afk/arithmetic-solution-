"""Tests for SSE fallback (Phase 63)."""
import threading
import time

from web.backend.sse import subscribe, unsubscribe, broadcast, subscriber_count


def test_subscribe_unsubscribe():
    ch = "test-channel-1"
    sub_id, q = subscribe(ch)
    assert subscriber_count(ch) >= 1
    unsubscribe(ch, sub_id)
    assert subscriber_count(ch) == 0


def test_broadcast_delivers():
    ch = "test-channel-2"
    sub_id, q = subscribe(ch)
    try:
        n = broadcast(ch, "ping", {"hello": "world"})
        assert n >= 1
        evt = q.get(timeout=1)
        assert evt["event"] == "ping"
        assert evt["data"] == {"hello": "world"}
    finally:
        unsubscribe(ch, sub_id)


def test_broadcast_with_no_subscribers():
    n = broadcast("empty-channel", "ping", {})
    assert n == 0


def test_channels_endpoint(client):
    r = client.get("/api/events/channels")
    assert r.status_code == 200
    assert "channels" in r.get_json()


def test_broadcast_endpoint_requires_auth(client):
    r = client.post("/api/events/broadcast", json={
        "channel": "x", "event": "y", "data": {},
    })
    assert r.status_code == 401


def test_broadcast_endpoint_authenticated(client):
    tok = client.post("/api/auth/register", json={
        "username": "sse_user", "email": "sse@example.com", "password": "secret123",
    }).get_json()["token"]
    r = client.post("/api/events/broadcast",
                    json={"channel": "test-x", "event": "hello", "data": {"n": 1}},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert "delivered" in r.get_json()
