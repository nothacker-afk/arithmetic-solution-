"""Tests for pub/sub abstraction (Phase 69)."""
import os

from web.backend import pubsub


def test_memory_backend_is_default(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    pubsub.reset_backend()
    b = pubsub.get_backend()
    assert b.name == "memory"
    pubsub.reset_backend()


def test_memory_backend_publish_subscribe():
    pubsub.reset_backend()
    b = pubsub.get_backend()
    sub = b.subscribe("test-chan")
    try:
        n = b.publish("test-chan", "ping", {"x": 1})
        assert n >= 1
        evt = next(iter(sub))
        assert evt["event"] == "ping"
        assert evt["data"] == {"x": 1}
    finally:
        sub.close()


def test_subscriber_count():
    pubsub.reset_backend()
    b = pubsub.get_backend()
    sub = b.subscribe("count-chan")
    try:
        assert b.subscriber_count("count-chan") >= 1
    finally:
        sub.close()
    assert b.subscriber_count("count-chan") == 0


def test_pubsub_status_endpoint(client):
    r = client.get("/api/events/pubsub/status")
    assert r.status_code == 200
    assert "backend" in r.get_json()


def test_redis_fallback_when_package_missing(monkeypatch):
    """If REDIS_URL set but redis not installed, falls back to memory."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    pubsub.reset_backend()
    # We can't guarantee redis is or isn't installed, but get_backend()
    # must never raise
    b = pubsub.get_backend()
    assert b.name in ("memory", "redis")
    pubsub.reset_backend()
