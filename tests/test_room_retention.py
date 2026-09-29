"""Tests for room retention overrides (Phase 84)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_default_retention(client):
    tok = _reg(client, "rr_a")
    r = client.get("/api/rooms/any-room/retention", headers=_auth(tok))
    assert r.status_code == 200
    body = r.get_json()
    assert body["is_custom"] is False
    assert body["chat_days"] is None


def test_set_requires_owner(client):
    a = _reg(client, "rr_b1")
    b = _reg(client, "rr_b2")
    client.post("/api/rooms/rr-room/claim", json={}, headers=_auth(a))
    r = client.put("/api/rooms/rr-room/retention",
                   json={"chat_days": 30}, headers=_auth(b))
    assert r.status_code == 403


def test_set_and_get(client):
    tok = _reg(client, "rr_c")
    client.post("/api/rooms/rr-room2/claim", json={}, headers=_auth(tok))
    r = client.put("/api/rooms/rr-room2/retention",
                   json={"chat_days": 30, "audit_days": 90},
                   headers=_auth(tok))
    assert r.status_code == 200
    body = r.get_json()
    assert body["chat_days"] == 30
    assert body["audit_days"] == 90

    r = client.get("/api/rooms/rr-room2/retention", headers=_auth(tok))
    assert r.get_json()["chat_days"] == 30


def test_invalid_days(client):
    tok = _reg(client, "rr_d")
    client.post("/api/rooms/rr-room3/claim", json={}, headers=_auth(tok))
    r = client.put("/api/rooms/rr-room3/retention",
                   json={"chat_days": -1}, headers=_auth(tok))
    assert r.status_code == 400
    r = client.put("/api/rooms/rr-room3/retention",
                   json={"chat_days": 100000}, headers=_auth(tok))
    assert r.status_code == 400


def test_reset(client):
    tok = _reg(client, "rr_e")
    client.post("/api/rooms/rr-room4/claim", json={}, headers=_auth(tok))
    client.put("/api/rooms/rr-room4/retention",
               json={"chat_days": 30}, headers=_auth(tok))
    r = client.delete("/api/rooms/rr-room4/retention", headers=_auth(tok))
    assert r.status_code == 200
    r = client.get("/api/rooms/rr-room4/retention", headers=_auth(tok))
    assert r.get_json()["is_custom"] is False


def test_reset_missing_room(client):
    tok = _reg(client, "rr_f")
    r = client.delete("/api/rooms/never-existed/retention", headers=_auth(tok))
    assert r.status_code == 404
