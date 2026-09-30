"""Tests for shareable calculations (Phase 88)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@x.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_save_requires_auth(client):
    assert client.post("/api/calc/save",
                       json={"expression": "1+1", "result": "2"}).status_code == 401


def test_save_and_view(client):
    tok = _reg(client, "cs_a")
    r = client.post("/api/calc/save", json={
        "expression": "2 + 2", "result": "4", "is_public": True,
    }, headers=_auth(tok))
    assert r.status_code == 201
    calc_id = r.get_json()["id"]

    r = client.get(f"/api/calc/saved/{calc_id}")
    assert r.status_code == 200
    assert r.get_json()["expression"] == "2 + 2"


def test_private_hidden(client):
    tok1 = _reg(client, "cs_b1")
    tok2 = _reg(client, "cs_b2")
    cid = client.post("/api/calc/save", json={
        "expression": "secret", "result": "1", "is_public": False,
    }, headers=_auth(tok1)).get_json()["id"]

    r = client.get(f"/api/calc/saved/{cid}", headers=_auth(tok2))
    assert r.status_code == 404


def test_list_saved(client):
    tok = _reg(client, "cs_c")
    client.post("/api/calc/save", json={"expression": "a", "result": "1"},
                headers=_auth(tok))
    client.post("/api/calc/save", json={"expression": "b", "result": "2"},
                headers=_auth(tok))
    r = client.get("/api/calc/saved", headers=_auth(tok))
    assert len(r.get_json()["calculations"]) == 2


def test_delete(client):
    tok = _reg(client, "cs_d")
    cid = client.post("/api/calc/save", json={"expression": "x", "result": "1"},
                      headers=_auth(tok)).get_json()["id"]
    assert client.delete(f"/api/calc/saved/{cid}",
                         headers=_auth(tok)).status_code == 200


def test_invalid_id(client):
    assert client.get("/api/calc/saved/not-hex").status_code == 400
