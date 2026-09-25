"""Tests for the admin dashboard (Phase 16)."""
import pytest


def _register(client, username):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secret123",
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"], r.get_json()["user_id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------
# Auth gates
# ---------------------------------------------------------------------
def test_stats_requires_auth(client):
    assert client.get("/api/admin/stats").status_code == 401


def test_stats_requires_admin(client):
    """Second user is not admin (admin is user id 1)."""
    _register(client, "first_admin")       # id=1 (admin)
    tok2, _ = _register(client, "regular") # id=2 (not admin)
    r = client.get("/api/admin/stats", headers=_auth(tok2))
    assert r.status_code == 403


def test_admin_can_access(client):
    tok, uid = _register(client, "sole_admin")
    assert uid == 1
    r = client.get("/api/admin/stats", headers=_auth(tok))
    assert r.status_code == 200


# ---------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------
def test_stats_shape(client):
    tok, _ = _register(client, "admin1")
    r = client.get("/api/admin/stats", headers=_auth(tok))
    assert r.status_code == 200
    data = r.get_json()
    for key in ("users", "rooms", "room_members", "chat_messages",
                "calculations", "files", "audit_entries", "invites"):
        assert key in data
    assert data["users"] >= 1
    assert data["files"]["count"] >= 0
    assert data["files"]["total_bytes"] >= 0


# ---------------------------------------------------------------------
# Server info
# ---------------------------------------------------------------------
def test_server_info(client):
    tok, _ = _register(client, "admin2")
    r = client.get("/api/admin/server-info", headers=_auth(tok))
    assert r.status_code == 200
    data = r.get_json()
    assert data["version"] == "0.16.0"
    assert "python" in data
    assert "platform" in data
    assert data["db_backend"] in ("sqlite", "postgres")
    assert data["uptime_seconds"] >= 0
    assert data["admin_user_id"] == 1


# ---------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------
def test_users_list(client):
    tok, _ = _register(client, "admin3")
    _register(client, "user_a")
    _register(client, "user_b")
    r = client.get("/api/admin/users", headers=_auth(tok))
    assert r.status_code == 200
    usernames = [u["username"] for u in r.get_json()["users"]]
    assert "admin3" in usernames
    assert "user_a" in usernames
    assert "user_b" in usernames


def test_users_limit(client):
    tok, _ = _register(client, "admin4")
    for i in range(5):
        _register(client, f"u{i}")
    r = client.get("/api/admin/users?limit=2", headers=_auth(tok))
    assert len(r.get_json()["users"]) == 2


# ---------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------
def test_rooms_empty(client):
    tok, _ = _register(client, "admin5")
    r = client.get("/api/admin/rooms", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["rooms"] == []
    assert r.get_json()["unclaimed_rooms"] == []


def test_rooms_with_data(client):
    tok, _ = _register(client, "admin6")
    # Claim two rooms
    client.post("/api/rooms/r-a/claim", json={}, headers=_auth(tok))
    client.post("/api/rooms/r-b/claim", json={}, headers=_auth(tok))
    # Add a chat message to an unclaimed room
    client.post("/api/chat/open-room", json={"username": "x", "body": "hi"})

    r = client.get("/api/admin/rooms", headers=_auth(tok))
    data = r.get_json()
    names = {room["name"] for room in data["rooms"]}
    assert {"r-a", "r-b"} <= names
    assert "open-room" in data["unclaimed_rooms"]


# ---------------------------------------------------------------------
# Audit viewer
# ---------------------------------------------------------------------
def test_audit_list_shape(client):
    tok, _ = _register(client, "admin7")
    r = client.get("/api/admin/audit", headers=_auth(tok))
    assert r.status_code == 200
    data = r.get_json()
    assert "entries" in data
    assert "actions" in data
    assert "count" in data
    assert "auth.register" in data["actions"]


def test_audit_filter_by_action(client):
    tok, _ = _register(client, "admin8")
    client.post("/api/rooms/filt-room/claim", json={}, headers=_auth(tok))

    r = client.get("/api/admin/audit?action=room.claim", headers=_auth(tok))
    assert r.status_code == 200
    for e in r.get_json()["entries"]:
        assert e["action"] == "room.claim"


def test_audit_filter_by_status(client):
    tok, _ = _register(client, "admin9")
    # Trigger a failed login
    client.post("/api/auth/login", json={
        "username": "admin9", "password": "wrongpass",
    })
    r = client.get("/api/admin/audit?status=failed", headers=_auth(tok))
    entries = r.get_json()["entries"]
    assert any(e["action"] == "auth.login" for e in entries)
    for e in entries:
        assert e["status"] == "failed"


def test_audit_clear(client):
    tok, _ = _register(client, "admin10")
    # Should be some entries by now
    before = client.get("/api/admin/audit", headers=_auth(tok)).get_json()["count"]
    assert before >= 1

    r = client.delete("/api/admin/audit", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["deleted_count"] >= 1

    after = client.get("/api/admin/audit", headers=_auth(tok)).get_json()["count"]
    # The DELETE itself was logged, so count should be exactly 1 (or close)
    assert after < before


# ---------------------------------------------------------------------
# Metrics JSON
# ---------------------------------------------------------------------
def test_metrics_json(client):
    tok, _ = _register(client, "admin11")
    client.get("/api/health")  # generate a request
    r = client.get("/api/admin/metrics", headers=_auth(tok))
    assert r.status_code == 200
    data = r.get_json()
    assert "uptime_seconds" in data
    assert isinstance(data["requests_total"], list)
    assert isinstance(data["errors_total"], dict)


# ---------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------
def test_admin_page_served(client):
    r = client.get("/admin")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Admin Dashboard" in body
    assert "audit" in body.lower()
