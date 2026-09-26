"""Tests for user status (Phase 55)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_status_requires_auth(client):
    assert client.get("/api/status/me").status_code == 401


def test_default_status(client):
    tok = _reg(client, "st_a")
    r = client.get("/api/status/me", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["state"] == "available"


def test_set_status(client):
    tok = _reg(client, "st_b")
    r = client.put("/api/status/me",
                   json={"state": "busy", "emoji": "💻", "message": "coding"},
                   headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["state"] == "busy"

    r = client.get("/api/status/me", headers=_auth(tok))
    assert r.get_json()["emoji"] == "💻"
    assert r.get_json()["message"] == "coding"


def test_invalid_state(client):
    tok = _reg(client, "st_c")
    r = client.put("/api/status/me", json={"state": "nonsense"}, headers=_auth(tok))
    assert r.status_code == 400


def test_get_other_user_status(client):
    _reg(client, "st_target")
    tok2 = _reg(client, "st_looker")
    client.put("/api/status/me", json={"state": "away"}, headers=_auth(
        client.post("/api/auth/login", json={
            "username": "st_target", "password": "secret123",
        }).get_json()["token"]))

    r = client.get("/api/status/user/st_target", headers=_auth(tok2))
    assert r.status_code == 200
    assert r.get_json()["state"] == "away"


def test_batch_status(client):
    t1 = _reg(client, "st_x1")
    t2 = _reg(client, "st_x2")
    me1 = client.get("/api/auth/me", headers=_auth(t1)).get_json()
    me2 = client.get("/api/auth/me", headers=_auth(t2)).get_json()

    r = client.get(f"/api/status/users?ids={me1['id']},{me2['id']}", headers=_auth(t1))
    assert r.status_code == 200
    statuses = r.get_json()["statuses"]
    assert str(me1["id"]) in statuses
    assert str(me2["id"]) in statuses
