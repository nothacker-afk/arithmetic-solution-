"""Tests for message pinning (Phase 51)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_pin_requires_auth(client):
    assert client.get("/api/rooms/x/pins").status_code == 401


def test_pin_and_list(client):
    tok = _reg(client, "pin_a")
    msg = client.post("/api/chat/pin-room", json={"username": "pin_a", "body": "important"}).get_json()

    r = client.post("/api/rooms/pin-room/pins",
                    json={"message_id": msg["id"], "note": "read this"},
                    headers=_auth(tok))
    assert r.status_code == 201

    r = client.get("/api/rooms/pin-room/pins", headers=_auth(tok))
    assert r.get_json()["count"] == 1
    assert r.get_json()["pins"][0]["note"] == "read this"


def test_pin_unknown_message(client):
    tok = _reg(client, "pin_b")
    r = client.post("/api/rooms/pin-room2/pins",
                    json={"message_id": 99999}, headers=_auth(tok))
    assert r.status_code == 404


def test_pin_idempotent_conflict(client):
    tok = _reg(client, "pin_c")
    msg = client.post("/api/chat/pin-room3", json={"username": "pin_c", "body": "x"}).get_json()
    client.post("/api/rooms/pin-room3/pins", json={"message_id": msg["id"]}, headers=_auth(tok))
    r = client.post("/api/rooms/pin-room3/pins", json={"message_id": msg["id"]}, headers=_auth(tok))
    assert r.status_code == 409


def test_unpin(client):
    tok = _reg(client, "pin_d")
    msg = client.post("/api/chat/pin-room4", json={"username": "pin_d", "body": "x"}).get_json()
    client.post("/api/rooms/pin-room4/pins", json={"message_id": msg["id"]}, headers=_auth(tok))
    r = client.delete(f"/api/rooms/pin-room4/pins/{msg['id']}", headers=_auth(tok))
    assert r.status_code == 200
    assert client.get("/api/rooms/pin-room4/pins", headers=_auth(tok)).get_json()["count"] == 0


def test_invalid_room(client):
    tok = _reg(client, "pin_e")
    assert client.get("/api/rooms/bad room/pins", headers=_auth(tok)).status_code == 400
