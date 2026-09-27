"""Tests for Web Push (Phase 79)."""
import os


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_vapid_key_unconfigured(client, monkeypatch):
    for k in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY"):
        monkeypatch.delenv(k, raising=False)
    r = client.get("/api/push/vapid-public-key")
    assert r.status_code == 503


def test_vapid_key_configured(client, monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "test-public-key")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "test-private-key")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:test@example.com")
    r = client.get("/api/push/vapid-public-key")
    assert r.status_code == 200
    assert r.get_json()["public_key"] == "test-public-key"


def test_subscribe_requires_auth(client):
    r = client.post("/api/push/subscribe", json={})
    assert r.status_code == 401


def test_subscribe_valid(client):
    tok = _reg(client, "wp_a")
    r = client.post("/api/push/subscribe", json={
        "endpoint": "https://push.example.com/abc123",
        "keys": {"p256dh": "base64-p256dh", "auth": "base64-auth"},
    }, headers=_auth(tok))
    assert r.status_code == 201
    assert r.get_json()["subscribed"] is True


def test_subscribe_missing_fields(client):
    tok = _reg(client, "wp_b")
    r = client.post("/api/push/subscribe", json={"endpoint": "x"},
                    headers=_auth(tok))
    assert r.status_code == 400


def test_list_subscriptions_hides_endpoint(client):
    tok = _reg(client, "wp_c")
    client.post("/api/push/subscribe", json={
        "endpoint": "https://push.example.com/abc-very-long-endpoint-here-1234567890",
        "keys": {"p256dh": "x", "auth": "y"},
    }, headers=_auth(tok))
    r = client.get("/api/push/subscriptions", headers=_auth(tok))
    subs = r.get_json()["subscriptions"]
    assert len(subs) == 1
    assert "endpoint" not in subs[0]
    assert subs[0]["endpoint_prefix"].endswith("…")


def test_unsubscribe(client):
    tok = _reg(client, "wp_d")
    ep = "https://push.example.com/xyz"
    client.post("/api/push/subscribe", json={
        "endpoint": ep, "keys": {"p256dh": "x", "auth": "y"},
    }, headers=_auth(tok))
    r = client.delete("/api/push/subscribe",
                      json={"endpoint": ep}, headers=_auth(tok))
    assert r.status_code == 200


def test_test_endpoint_unconfigured(client, monkeypatch):
    for k in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY"):
        monkeypatch.delenv(k, raising=False)
    tok = _reg(client, "wp_e")
    r = client.post("/api/push/test", json={}, headers=_auth(tok))
    assert r.status_code == 503
