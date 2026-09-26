"""Tests for disappearing messages (Phase 39)."""
from datetime import datetime, timezone

from web.backend import jobs


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_room_ttl_default_zero(client):
    r = client.get("/api/chat/ttl-room/ttl")
    assert r.status_code == 200
    assert r.get_json()["ttl_seconds"] == 0


def test_set_room_ttl(client):
    r = client.put("/api/chat/ttl-room/ttl", json={"ttl_seconds": 3600})
    assert r.status_code == 200
    assert r.get_json()["ttl_seconds"] == 3600

    r = client.get("/api/chat/ttl-room/ttl")
    assert r.get_json()["ttl_seconds"] == 3600


def test_ttl_applied_to_new_messages(client):
    client.put("/api/chat/ttl-room2/ttl", json={"ttl_seconds": 60})
    client.post("/api/chat/ttl-room2", json={
        "username": "someone", "body": "expires soon"})
    rows = client.get("/api/chat/ttl-room2").get_json()["messages"]
    assert rows[0]["expires_at"] is not None


def test_ttl_out_of_range(client):
    r = client.put("/api/chat/bad-room/ttl", json={"ttl_seconds": -1})
    assert r.status_code == 400
    r = client.put("/api/chat/bad-room/ttl", json={"ttl_seconds": 99999999})
    assert r.status_code == 400


def test_jobs_purge_expired(client):
    """Backdate an expired message and run jobs.run_retention."""
    client.put("/api/chat/purge-room/ttl", json={"ttl_seconds": 60})
    client.post("/api/chat/purge-room", json={"username": "x", "body": "y"})

    # Backdate expires_at
    from web.backend.database import get_db
    past = (datetime.now(timezone.utc).replace(year=2020)).isoformat()
    with get_db() as conn:
        conn.execute("UPDATE chat_messages SET expires_at = ?", (past,))

    deleted = jobs.run_retention()
    assert deleted.get("expired_chat", 0) >= 1


def test_dm_thread_ttl(client):
    a = _reg(client, "ttl_dm_a")
    _b = _reg(client, "ttl_dm_b")
    tid = client.post("/api/dms/threads", json={"username": "ttl_dm_b"},
                      headers=_auth(a)).get_json()["thread_id"]

    r = client.put(f"/api/dms/threads/{tid}/ttl",
                   json={"ttl_seconds": 300}, headers=_auth(a))
    assert r.status_code == 200
    assert r.get_json()["ttl_seconds"] == 300
