"""Tests for room-scoped search (Phase 44)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_search_within_room(client):
    a = _reg(client, "rs_a")
    # Post messages in two rooms
    client.post("/api/chat/rs-room-a", json={"username": "rs_a", "body": "unique_needle_here"})
    client.post("/api/chat/rs-room-b", json={"username": "rs_a", "body": "unique_needle_here"})

    r = client.get("/api/search?q=unique_needle_here&room=rs-room-a",
                   headers=_auth(a))
    assert r.status_code == 200
    results = r.get_json()["results"]
    # All chat results must be from rs-room-a
    for x in results:
        if x["kind"] == "chat":
            assert x["room_id"] == "rs-room-a"


def test_search_no_room_returns_all(client):
    a = _reg(client, "rs_a2")
    client.post("/api/chat/rs-r1", json={"username": "rs_a2", "body": "needle_two"})
    client.post("/api/chat/rs-r2", json={"username": "rs_a2", "body": "needle_two"})

    r = client.get("/api/search?q=needle_two", headers=_auth(a))
    results = [x for x in r.get_json()["results"] if x["kind"] == "chat"]
    rooms = {x["room_id"] for x in results}
    assert len(rooms) >= 2
