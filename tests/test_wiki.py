"""Tests for room wiki (Phase 52)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_wiki_requires_auth(client):
    assert client.get("/api/rooms/x/wiki").status_code == 401


def test_create_and_list(client):
    tok = _reg(client, "wiki_a")
    r = client.post("/api/rooms/wiki-room/wiki",
                    json={"title": "Getting started", "body": "Hello world"},
                    headers=_auth(tok))
    assert r.status_code == 201
    assert r.get_json()["slug"] == "getting-started"

    r = client.get("/api/rooms/wiki-room/wiki", headers=_auth(tok))
    assert r.get_json()["count"] == 1


def test_get_page(client):
    tok = _reg(client, "wiki_b")
    client.post("/api/rooms/wiki-room2/wiki",
                json={"title": "Page", "body": "content"},
                headers=_auth(tok))
    r = client.get("/api/rooms/wiki-room2/wiki/page", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["body"] == "content"


def test_update_page(client):
    tok = _reg(client, "wiki_c")
    client.post("/api/rooms/wiki-room3/wiki",
                json={"title": "Edit me", "body": "v1"},
                headers=_auth(tok))
    r = client.put("/api/rooms/wiki-room3/wiki/edit-me",
                   json={"body": "v2"}, headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["body"] == "v2"


def test_delete_page(client):
    tok = _reg(client, "wiki_d")
    client.post("/api/rooms/wiki-room4/wiki",
                json={"title": "Delete me", "body": "x"},
                headers=_auth(tok))
    r = client.delete("/api/rooms/wiki-room4/wiki/delete-me", headers=_auth(tok))
    assert r.status_code == 200
    assert client.get("/api/rooms/wiki-room4/wiki/delete-me",
                      headers=_auth(tok)).status_code == 404


def test_missing_title(client):
    tok = _reg(client, "wiki_e")
    r = client.post("/api/rooms/wiki-room5/wiki", json={"body": "x"},
                    headers=_auth(tok))
    assert r.status_code == 400


def test_duplicate_slugs_get_suffixed(client):
    tok = _reg(client, "wiki_f")
    client.post("/api/rooms/wiki-room6/wiki", json={"title": "Same", "body": "1"},
                headers=_auth(tok))
    client.post("/api/rooms/wiki-room6/wiki", json={"title": "Same", "body": "2"},
                headers=_auth(tok))
    r = client.get("/api/rooms/wiki-room6/wiki", headers=_auth(tok))
    slugs = [p["slug"] for p in r.get_json()["pages"]]
    assert "same" in slugs
    assert any(s != "same" for s in slugs)
