"""Tests for room discovery (Phase 42)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _claim(client, tok, room):
    return client.post(f"/api/rooms/{room}/claim", json={}, headers=_auth(tok))


def test_browse_public_empty(client):
    r = client.get("/api/discover/rooms")
    assert r.status_code == 200
    assert r.get_json()["rooms"] == []


def test_publish_and_browse(client):
    a = _reg(client, "disc_a")
    _claim(client, a, "disc-room")

    r = client.post("/api/rooms/disc-room/publish",
                    json={"description": "A test room", "tags": "test,math"},
                    headers=_auth(a))
    assert r.status_code == 200
    assert r.get_json()["published"] is True

    r = client.get("/api/discover/rooms")
    rooms = r.get_json()["rooms"]
    assert len(rooms) == 1
    assert rooms[0]["name"] == "disc-room"
    assert rooms[0]["description"] == "A test room"


def test_publish_requires_owner(client):
    a = _reg(client, "disc_a2")
    b = _reg(client, "disc_b2")
    _claim(client, a, "disc-room2")

    r = client.post("/api/rooms/disc-room2/publish", json={}, headers=_auth(b))
    assert r.status_code == 403


def test_unpublish(client):
    a = _reg(client, "disc_a3")
    _claim(client, a, "disc-room3")
    client.post("/api/rooms/disc-room3/publish", json={}, headers=_auth(a))
    r = client.delete("/api/rooms/disc-room3/publish", headers=_auth(a))
    assert r.status_code == 200
    assert client.get("/api/discover/rooms").get_json()["rooms"] == []


def test_search_by_query(client):
    a = _reg(client, "disc_a4")
    _claim(client, a, "math-room")
    client.post("/api/rooms/math-room/publish",
                json={"description": "algebra and geometry", "tags": "math"},
                headers=_auth(a))

    r = client.get("/api/discover/rooms?q=algebra")
    assert len(r.get_json()["rooms"]) == 1

    r = client.get("/api/discover/rooms?q=history")
    assert r.get_json()["rooms"] == []


def test_search_by_tag(client):
    a = _reg(client, "disc_a5")
    _claim(client, a, "tagged-room")
    client.post("/api/rooms/tagged-room/publish",
                json={"tags": "physics,fun"}, headers=_auth(a))

    r = client.get("/api/discover/rooms?tag=physics")
    assert len(r.get_json()["rooms"]) == 1

    r = client.get("/api/discover/rooms?tag=biology")
    assert r.get_json()["rooms"] == []


def test_room_detail(client):
    a = _reg(client, "disc_a6")
    _claim(client, a, "detail-room")
    client.post("/api/rooms/detail-room/publish",
                json={"description": "Cool room", "tags": "cool"},
                headers=_auth(a))

    r = client.get("/api/discover/rooms/detail-room")
    assert r.status_code == 200
    assert r.get_json()["description"] == "Cool room"

    # Unpublished room
    r = client.get("/api/discover/rooms/nonexistent")
    assert r.status_code == 404
