"""Tests for event reminders (Phase 73)."""
from datetime import datetime, timedelta, timezone


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _make_event(client, tok, room="rem-room", hours=2):
    return client.post(f"/api/rooms/{room}/events",
                       json={"title": "Standup",
                             "starts_at": (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()},
                       headers=_auth(tok)).get_json()["id"]


def test_add_reminder(client):
    tok = _reg(client, "rem_a")
    eid = _make_event(client, tok)
    r = client.post(f"/api/rooms/rem-room/events/{eid}/reminders",
                    json={"minutes_before": 15}, headers=_auth(tok))
    assert r.status_code == 201


def test_reminder_invalid_minutes(client):
    tok = _reg(client, "rem_b")
    eid = _make_event(client, tok, "rem-room2")
    r = client.post(f"/api/rooms/rem-room2/events/{eid}/reminders",
                    json={"minutes_before": 7}, headers=_auth(tok))
    assert r.status_code == 400


def test_list_and_delete(client):
    tok = _reg(client, "rem_c")
    eid = _make_event(client, tok, "rem-room3")
    client.post(f"/api/rooms/rem-room3/events/{eid}/reminders",
                json={"minutes_before": 30}, headers=_auth(tok))
    r = client.get(f"/api/rooms/rem-room3/events/{eid}/reminders", headers=_auth(tok))
    assert len(r.get_json()["reminders"]) == 1
    r = client.delete(f"/api/rooms/rem-room3/events/{eid}/reminders/30", headers=_auth(tok))
    assert r.status_code == 200


def test_duplicate_reminder_conflict(client):
    tok = _reg(client, "rem_d")
    eid = _make_event(client, tok, "rem-room4")
    client.post(f"/api/rooms/rem-room4/events/{eid}/reminders",
                json={"minutes_before": 15}, headers=_auth(tok))
    r = client.post(f"/api/rooms/rem-room4/events/{eid}/reminders",
                    json={"minutes_before": 15}, headers=_auth(tok))
    assert r.status_code == 409


def test_tick_dispatches_due(client):
    """Scheduling a 1440-minute reminder for an event 1h away = due immediately."""
    from web.backend.event_reminders import tick
    tok = _reg(client, "rem_e")
    eid = _make_event(client, tok, "rem-room5", hours=1)
    client.post(f"/api/rooms/rem-room5/events/{eid}/reminders",
                json={"minutes_before": 1440}, headers=_auth(tok))
    n = tick()
    assert n >= 1
