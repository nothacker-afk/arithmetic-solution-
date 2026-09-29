"""Tests for global search (Phase 85)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_global_search_requires_auth(client):
    assert client.get("/api/search/global?q=x").status_code == 401


def test_global_search_empty(client):
    tok = _reg(client, "gs_a")
    r = client.get("/api/search/global?q=", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["count"] == 0


def test_global_search_finds_chat(client):
    tok = _reg(client, "gs_b")
    client.post("/api/chat/gs-room", json={"username": "gs_b", "body": "unique_gs_needle"})
    r = client.get("/api/search/global?q=unique_gs_needle", headers=_auth(tok))
    results = r.get_json()["results"]
    assert any(x["kind"] == "chat" for x in results)


def test_global_search_finds_calculation(client):
    tok = _reg(client, "gs_c")
    client.post("/api/history", json={"expression": "42*17", "result": "714"},
                headers=_auth(tok))
    r = client.get("/api/search/global?q=714", headers=_auth(tok))
    assert any(x["kind"] == "calc" for x in r.get_json()["results"])


def test_global_search_kinds_filter(client):
    tok = _reg(client, "gs_d")
    client.post("/api/chat/gs-room2", json={"username": "gs_d", "body": "needle_xyz"})
    r = client.get("/api/search/global?q=needle_xyz&kinds=calc", headers=_auth(tok))
    assert all(x["kind"] == "calc" for x in r.get_json()["results"])


def test_global_search_invalid_kind(client):
    tok = _reg(client, "gs_e")
    r = client.get("/api/search/global?q=x&kinds=wat", headers=_auth(tok))
    assert r.status_code == 400


def test_global_search_isolates_other_users_calcs(client):
    tok1 = _reg(client, "gs_f1")
    tok2 = _reg(client, "gs_f2")
    client.post("/api/history", json={"expression": "private_xyz", "result": "1"},
                headers=_auth(tok1))
    r = client.get("/api/search/global?q=private_xyz", headers=_auth(tok2))
    calcs = [x for x in r.get_json()["results"] if x["kind"] == "calc"]
    assert calcs == []
