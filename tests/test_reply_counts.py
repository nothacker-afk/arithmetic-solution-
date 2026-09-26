"""Tests for reply counts (Phase 35)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_reply_count_in_list(client):
    _reg(client, "rc_user1")
    parent = client.post("/api/chat/rc-room", json={
        "username": "rc_user1", "body": "root"}).get_json()
    for i in range(3):
        client.post("/api/chat/rc-room", json={
            "username": "rc_user1", "body": f"r{i}", "parent_id": parent["id"]})

    r = client.get("/api/chat/rc-room")
    messages = r.get_json()["messages"]
    root = [m for m in messages if m["id"] == parent["id"]][0]
    assert root["reply_count"] == 3
