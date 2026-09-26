"""Tests for chat threads (Phase 33)."""


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def test_reply_creates_threaded_message(client):
    tok = _reg(client, "thread_user1")
    parent = client.post("/api/chat/thread-room", json={
        "username": "thread_user1", "body": "root",
    }).get_json()

    r = client.post("/api/chat/thread-room", json={
        "username": "thread_user1", "body": "reply", "parent_id": parent["id"],
    })
    assert r.status_code == 201
    assert r.get_json()["parent_id"] == parent["id"]


def test_reply_to_missing_parent(client):
    tok = _reg(client, "thread_user2")
    r = client.post("/api/chat/thread-room2", json={
        "username": "thread_user2", "body": "orphan", "parent_id": 99999,
    })
    assert r.status_code == 404


def test_reply_to_other_room_parent(client):
    _reg(client, "thread_user3")
    p = client.post("/api/chat/room-a", json={
        "username": "thread_user3", "body": "in-a",
    }).get_json()
    r = client.post("/api/chat/room-b", json={
        "username": "thread_user3", "body": "wrong-room",
        "parent_id": p["id"],
    })
    assert r.status_code == 404


def test_list_replies(client):
    _reg(client, "thread_user4")
    p = client.post("/api/chat/thread-room3", json={
        "username": "thread_user4", "body": "root",
    }).get_json()
    for i in range(3):
        client.post("/api/chat/thread-room3", json={
            "username": "thread_user4", "body": f"r{i}", "parent_id": p["id"],
        })

    r = client.get(f"/api/chat/thread-room3/{p['id']}/replies")
    assert r.status_code == 200
    assert len(r.get_json()["replies"]) == 3


def test_replies_endpoint_404(client):
    r = client.get("/api/chat/any-room/99999/replies")
    assert r.status_code == 404
