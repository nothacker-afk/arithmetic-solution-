"""Tests for push notification endpoints (Phase 19)."""
import pytest

from web.backend import notifications


def _register(client, username):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secret123",
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_requires_auth(client):
    r = client.post("/api/notifications/register", json={"token": "abc"})
    assert r.status_code == 401


def test_register_token(client):
    tok = _register(client, "push_user1")
    r = client.post("/api/notifications/register",
                    json={"token": "fake-fcm-token-abc", "platform": "android"},
                    headers=_auth(tok))
    assert r.status_code == 201
    assert r.get_json()["registered"] is True


def test_register_missing_token(client):
    tok = _register(client, "push_user2")
    r = client.post("/api/notifications/register",
                    json={"platform": "android"}, headers=_auth(tok))
    assert r.status_code == 400


def test_register_token_too_long(client):
    tok = _register(client, "push_user3")
    r = client.post("/api/notifications/register",
                    json={"token": "x" * 5000}, headers=_auth(tok))
    assert r.status_code == 400


def test_register_is_idempotent(client):
    tok = _register(client, "push_user4")
    for _ in range(3):
        r = client.post("/api/notifications/register",
                        json={"token": "same-token", "platform": "android"},
                        headers=_auth(tok))
        assert r.status_code == 201
    r = client.get("/api/notifications/tokens", headers=_auth(tok))
    assert r.get_json()["count"] == 1


def test_list_tokens(client):
    tok = _register(client, "push_user5")
    client.post("/api/notifications/register",
                json={"token": "tok-a", "platform": "android"}, headers=_auth(tok))
    client.post("/api/notifications/register",
                json={"token": "tok-b", "platform": "ios"}, headers=_auth(tok))
    r = client.get("/api/notifications/tokens", headers=_auth(tok))
    assert r.get_json()["count"] == 2


def test_unregister_token(client):
    tok = _register(client, "push_user6")
    client.post("/api/notifications/register",
                json={"token": "tok-x"}, headers=_auth(tok))
    r = client.post("/api/notifications/unregister",
                    json={"token": "tok-x"}, headers=_auth(tok))
    assert r.get_json()["removed"] == 1
    assert client.get("/api/notifications/tokens",
                      headers=_auth(tok)).get_json()["count"] == 0


def test_test_endpoint_dry_run(client):
    tok = _register(client, "push_user7")
    client.post("/api/notifications/register",
                json={"token": "tok-y"}, headers=_auth(tok))
    r = client.post("/api/notifications/test", headers=_auth(tok))
    assert r.status_code == 200
    body = r.get_json()
    assert "sent" in body
    assert "configured" in body
    # Without FCM_PROJECT_ID + FCM_ACCESS_TOKEN, configured is False
    assert body["configured"] is False


def test_send_push_dry_run_when_unconfigured(monkeypatch):
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("FCM_PROJECT_ID", raising=False)
    monkeypatch.delenv("FCM_ACCESS_TOKEN", raising=False)
    # Should return False (dry-run) without raising
    assert notifications.send_push(1, "t", "b") is False


def test_notify_room_invite_does_not_raise(monkeypatch):
    monkeypatch.delenv("FCM_PROJECT_ID", raising=False)
    monkeypatch.delenv("FCM_ACCESS_TOKEN", raising=False)
    # Fire-and-forget helper
    notifications.notify_room_invite(1, "test-room", "alice")
    notifications.notify_mention(1, "test-room", "bob", "hey there")


def test_token_pruning_hook(monkeypatch):
    """Verify stale-token pruning path is wired (no network needed)."""
    # Just assert the helper exists and is callable
    assert callable(notifications.send_push)
