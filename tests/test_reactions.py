"""Tests for reactions (Phase 32)."""


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def test_react_requires_auth(client):
    r = client.post("/api/reactions", json={
        "kind": "chat", "message_id": 1, "emoji": "👍",
    })
    assert r.status_code == 401


def test_react_to_missing_message(client):
    tok = _reg(client, "react_user1")
    r = client.post("/api/reactions", json={
        "kind": "chat", "message_id": 99999, "emoji": "👍",
    }, headers=_auth(tok))
    assert r.status_code == 404


def test_react_invalid_kind(client):
    tok = _reg(client, "react_user2")
    r = client.post("/api/reactions", json={
        "kind": "wat", "message_id": 1, "emoji": "👍",
    }, headers=_auth(tok))
    assert r.status_code == 400


def test_react_invalid_emoji(client):
    tok = _reg(client, "react_user3")
    r = client.post("/api/reactions", json={
        "kind": "chat", "message_id": 1, "emoji": "💩",
    }, headers=_auth(tok))
    assert r.status_code == 400


def test_react_and_list(client):
    tok = _reg(client, "react_user4")
    msg = client.post("/api/chat/react-room", json={
        "username": "react_user4", "body": "hi",
    }).get_json()
    r = client.post("/api/reactions", json={
        "kind": "chat", "message_id": msg["id"], "emoji": "👍",
    }, headers=_auth(tok))
    assert r.status_code == 201

    r = client.get(f"/api/reactions?kind=chat&message_ids={msg['id']}",
                   headers=_auth(tok))
    data = r.get_json()["reactions"]
    assert str(msg["id"]) in data
    assert "👍" in data[str(msg["id"])]


def test_react_idempotent(client):
    tok = _reg(client, "react_user5")
    msg = client.post("/api/chat/react-room2", json={
        "username": "react_user5", "body": "hi",
    }).get_json()
    for _ in range(2):
        r = client.post("/api/reactions", json={
            "kind": "chat", "message_id": msg["id"], "emoji": "❤️",
        }, headers=_auth(tok))
        assert r.status_code == 201
    r = client.get(f"/api/reactions?kind=chat&message_ids={msg['id']}",
                   headers=_auth(tok))
    users = r.get_json()["reactions"][str(msg["id"])]["❤️"]
    # Only one entry despite two posts
    assert users.count(users[0]) == len(users)


def test_unreact(client):
    tok = _reg(client, "react_user6")
    msg = client.post("/api/chat/react-room3", json={
        "username": "react_user6", "body": "hi",
    }).get_json()
    client.post("/api/reactions", json={
        "kind": "chat", "message_id": msg["id"], "emoji": "🎉",
    }, headers=_auth(tok))
    r = client.delete("/api/reactions", json={
        "kind": "chat", "message_id": msg["id"], "emoji": "🎉",
    }, headers=_auth(tok))
    assert r.get_json()["removed"] == 1

    r = client.get(f"/api/reactions?kind=chat&message_ids={msg['id']}",
                   headers=_auth(tok))
    assert "🎉" not in (r.get_json()["reactions"][str(msg["id"])] or {})
