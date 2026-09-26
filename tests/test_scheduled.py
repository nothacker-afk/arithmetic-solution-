"""Tests for scheduled messages (Phase 46)."""
from datetime import datetime, timedelta, timezone

from web.backend import scheduled


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_schedule_requires_auth(client):
    r = client.post("/api/scheduled", json={
        "room_id": "r", "body": "hi",
        "send_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    })
    assert r.status_code == 401


def test_schedule_success(client):
    tok = _reg(client, "sched_user1")
    when = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    r = client.post("/api/scheduled", json={
        "room_id": "sched-room", "body": "hello later", "send_at": when,
    }, headers=_auth(tok))
    assert r.status_code == 201
    assert r.get_json()["room_id"] == "sched-room"


def test_schedule_rejects_past(client):
    tok = _reg(client, "sched_user2")
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    r = client.post("/api/scheduled", json={
        "room_id": "r", "body": "hi", "send_at": past,
    }, headers=_auth(tok))
    assert r.status_code == 400


def test_schedule_rejects_bad_time(client):
    tok = _reg(client, "sched_user3")
    r = client.post("/api/scheduled", json={
        "room_id": "r", "body": "hi", "send_at": "not-a-date",
    }, headers=_auth(tok))
    assert r.status_code == 400


def test_list_pending(client):
    tok = _reg(client, "sched_user4")
    when = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    client.post("/api/scheduled", json={"room_id": "r1", "body": "a", "send_at": when},
                headers=_auth(tok))
    client.post("/api/scheduled", json={"room_id": "r2", "body": "b", "send_at": when},
                headers=_auth(tok))
    r = client.get("/api/scheduled", headers=_auth(tok))
    assert len(r.get_json()["pending"]) == 2


def test_cancel_scheduled(client):
    tok = _reg(client, "sched_user5")
    when = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    s = client.post("/api/scheduled", json={"room_id": "r", "body": "x", "send_at": when},
                    headers=_auth(tok)).get_json()
    r = client.delete(f"/api/scheduled/{s['id']}", headers=_auth(tok))
    assert r.status_code == 200
    assert client.get("/api/scheduled", headers=_auth(tok)).get_json()["pending"] == []


def test_dispatch_due(client):
    tok = _reg(client, "sched_user6")
    # Schedule one 1 hour in the future, then dispatch with `now=+2h`
    when = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    client.post("/api/scheduled", json={"room_id": "due-room", "body": "boom", "send_at": when},
                headers=_auth(tok))

    # Dispatch with a fake future time
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    n = scheduled.dispatch_due(now=future)
    assert n >= 1

    # Message should be in the room
    rows = client.get("/api/chat/due-room").get_json()["messages"]
    assert any(m["body"] == "boom" for m in rows)
