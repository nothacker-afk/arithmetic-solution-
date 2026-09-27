"""Tests for wiki full-text search (Phase 80)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _page(client, tok, room, title, body):
    return client.post(f"/api/rooms/{room}/wiki",
                       json={"title": title, "body": body},
                       headers=_auth(tok)).get_json()


def test_search_requires_auth(client):
    r = client.get("/api/wiki/search?q=x")
    assert r.status_code == 401


def test_search_empty_query(client):
    tok = _reg(client, "ws_a")
    r = client.get("/api/wiki/search?q=", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["count"] == 0


def test_search_finds_page_by_body(client):
    tok = _reg(client, "ws_b")
    _page(client, tok, "ws-room", "Getting Started", "The answer is 42 forever.")
    r = client.get("/api/wiki/search?q=42", headers=_auth(tok))
    assert r.status_code == 200
    results = r.get_json()["results"]
    assert any(r_["title"] == "Getting Started" for r_ in results)


def test_search_finds_page_by_title(client):
    tok = _reg(client, "ws_c")
    _page(client, tok, "ws-room2", "UniqueTitleXYZ", "body text")
    r = client.get("/api/wiki/search?q=UniqueTitleXYZ", headers=_auth(tok))
    assert any(r_["title"] == "UniqueTitleXYZ" for r_ in r.get_json()["results"])


def test_search_filtered_by_room(client):
    tok = _reg(client, "ws_d")
    _page(client, tok, "room-alpha", "Doc A", "needle-string-here")
    _page(client, tok, "room-beta", "Doc B", "needle-string-here")

    r = client.get("/api/wiki/search?q=needle-string-here&room=room-alpha",
                   headers=_auth(tok))
    results = r.get_json()["results"]
    assert all(x["room_id"] == "room-alpha" for x in results)


def test_search_invalid_room(client):
    tok = _reg(client, "ws_e")
    r = client.get("/api/wiki/search?q=x&room=bad room", headers=_auth(tok))
    assert r.status_code == 400


def test_snippet_present(client):
    tok = _reg(client, "ws_f")
    _page(client, tok, "ws-room3", "Snippet test", "foo unique_snippet_marker bar baz")
    r = client.get("/api/wiki/search?q=unique_snippet_marker", headers=_auth(tok))
    results = r.get_json()["results"]
    assert results
    assert "unique_snippet_marker" in results[0]["snippet"]


def test_engine_reported(client):
    tok = _reg(client, "ws_g")
    _page(client, tok, "ws-room4", "x", "some text")
    r = client.get("/api/wiki/search?q=some", headers=_auth(tok))
    assert r.get_json()["engine"] in ("fts5", "like")
