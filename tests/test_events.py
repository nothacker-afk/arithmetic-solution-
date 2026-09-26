"""Tests for room events (Phase 54)."""
from datetime import datetime, timedelta, timezone


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _future_iso(hours=1):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def test_events_requires_auth(client):
    assert client.get("/api/rooms/x/events").status_code == 401


def test_create_and_list(client):
    tok = _reg(client, "ev_a")
    r = client.post("/api/rooms/ev-room/events",
                    json={"title": "Standup", "starts_at": _future_iso()},
                    headers=_auth(tok))
    assert r.status_code == 201
    assert r.get_json()["title"] == "Standup"

    r = client.get("/api/rooms/ev-room/events", headers=_auth(tok))
    assert len(r.get_json()["upcoming"]) == 1


def test_event_requires_title_and_time(client):
    tok = _reg(client, "ev_b")
    r = client.post("/api/rooms/ev-room2/events", json={}, headers=_auth(tok))
    assert r.status_code == 400

    r = client.post("/api/rooms/ev-room2/events",
                    json={"title": "x"}, headers=_auth(tok))
    assert r.status_code == 400


def test_rsvp(client):
    tok = _reg(client, "ev_c")
    ev = client.post("/api/rooms/ev-room3/events",
                     json={"title": "Party", "starts_at": _future_iso()},
                     headers=_auth(tok)).get_json()
    r = client.post(f"/api/rooms/ev-room3/events/{ev['id']}/rsvp",
                    json={"status": "going"}, headers=_auth(tok))
    assert r.status_code == 200

    r = client.get(f"/api/rooms/ev-room3/events/{ev['id']}", headers=_auth(tok))
    assert any(rs["status"] == "going" for rs in r.get_json()["rsvps"])


def test_rsvp_invalid_status(client):
    tok = _reg(client, "ev_d")
    ev = client.post("/api/rooms/ev-room4/events",
                     json={"title": "x", "starts_at": _future_iso()},
                     headers=_auth(tok)).get_json()
    r = client.post(f"/api/rooms/ev-room4/events/{ev['id']}/rsvp",
                    json={"status": "bogus"}, headers=_auth(tok))
    assert r.status_code == 400


def test_delete_only_creator(client):
    tok_a = _reg(client, "ev_e1")
    tok_b = _reg(client, "ev_e2")
    ev = client.post("/api/rooms/ev-room5/events",
                     json={"title": "y", "starts_at": _future_iso()},
                     headers=_auth(tok_a)).get_json()
    r = client.delete(f"/api/rooms/ev-room5/events/{ev['id']}", headers=_auth(tok_b))
    assert r.status_code == 403

    r = client.delete(f"/api/rooms/ev-room5/events/{ev['id']}", headers=_auth(tok_a))
    assert r.status_code == 200


def test_invalid_event_id(client):
    tok = _reg(client, "ev_f")
    r = client.get("/api/rooms/ev-room6/events/not-hex", headers=_auth(tok))
    assert r.status_code == 400
