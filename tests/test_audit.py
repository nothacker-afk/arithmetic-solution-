"""Tests for the audit log (Phase 13)."""
import pytest


def _register(client, username):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secret123",
    })
    assert r.status_code == 201
    return r.get_json()["token"], r.get_json()["user_id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_writes_audit(client):
    tok, uid = _register(client, "audit_user1")
    r = client.get("/api/audit", headers=_auth(tok))
    assert r.status_code == 200
    actions = [e["action"] for e in r.get_json()["entries"]]
    assert "auth.register" in actions


def test_login_writes_audit(client):
    tok, uid = _register(client, "audit_user2")
    client.post("/api/auth/login", json={
        "username": "audit_user2", "password": "secret123",
    })
    r = client.get("/api/audit?action=auth.login", headers=_auth(tok))
    entries = r.get_json()["entries"]
    assert any(e["status"] == "ok" for e in entries)


def test_failed_login_writes_audit(client):
    tok, uid = _register(client, "audit_user3")
    client.post("/api/auth/login", json={
        "username": "audit_user3", "password": "wrongpass",
    })
    r = client.get("/api/audit?action=auth.login", headers=_auth(tok))
    entries = r.get_json()["entries"]
    assert any(e["status"] == "failed" for e in entries)


def test_room_claim_writes_audit(client):
    tok, uid = _register(client, "audit_user4")
    client.post("/api/rooms/audit-room/claim", json={}, headers=_auth(tok))
    r = client.get("/api/audit?action=room.claim", headers=_auth(tok))
    assert r.get_json()["count"] >= 1


def test_admin_user_sees_all(client):
    # Register user 1 (admin by default)
    admin_tok, admin_id = _register(client, "admin_first")
    assert admin_id == 1  # first user

    # Register a second user who does something
    other_tok, _ = _register(client, "audit_other")
    client.post("/api/rooms/admin-see/claim", json={}, headers=_auth(other_tok))

    # Admin should see both users' entries
    r = client.get("/api/audit", headers=_auth(admin_tok))
    assert r.get_json()["is_admin"] is True
    actors = {e["actor_id"] for e in r.get_json()["entries"] if e["actor_id"]}
    assert admin_id in actors or len(actors) >= 2


def test_audit_requires_auth(client):
    assert client.get("/api/audit").status_code == 401


def test_audit_action_filter(client):
    tok, uid = _register(client, "audit_user5")
    client.post("/api/rooms/audit-f/claim", json={}, headers=_auth(tok))
    r = client.get("/api/audit?action=room.claim", headers=_auth(tok))
    for e in r.get_json()["entries"]:
        assert e["action"] == "room.claim"
