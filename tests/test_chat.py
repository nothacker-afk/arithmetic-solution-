"""Tests for the chat REST API."""
import pytest


def test_list_empty_room(client):
    r = client.get("/api/chat/test-room")
    assert r.status_code == 200
    body = r.get_json()
    assert body["room"] == "test-room"
    assert body["messages"] == []


def test_post_message(client):
    r = client.post("/api/chat/test-room", json={
        "username": "alice", "body": "hello world",
    })
    assert r.status_code == 201
    data = r.get_json()
    assert data["username"] == "alice"
    assert data["body"] == "hello world"
    assert data["encrypted"] == 0


def test_post_encrypted_message(client):
    r = client.post("/api/chat/test-room", json={
        "username": "alice",
        "body": "dGVzdC1jaXBoZXJ0ZXh0",
        "encrypted": True,
    })
    assert r.status_code == 201
    assert r.get_json()["encrypted"] == 1


def test_post_missing_body(client):
    r = client.post("/api/chat/test-room", json={"username": "alice"})
    assert r.status_code == 400


def test_post_missing_username(client):
    r = client.post("/api/chat/test-room", json={"body": "hi"})
    assert r.status_code == 400


def test_post_body_too_long(client):
    r = client.post("/api/chat/test-room", json={
        "username": "alice", "body": "x" * 5000,
    })
    assert r.status_code == 400


def test_invalid_room_name(client):
    r = client.get("/api/chat/bad%20room!")
    assert r.status_code == 400


def test_list_orders_oldest_first(client):
    for i in range(3):
        client.post("/api/chat/ordered", json={"username": "u", "body": f"msg{i}"})
    r = client.get("/api/chat/ordered")
    bodies = [m["body"] for m in r.get_json()["messages"]]
    assert bodies == ["msg0", "msg1", "msg2"]


def test_list_limit(client):
    for i in range(10):
        client.post("/api/chat/lim", json={"username": "u", "body": f"m{i}"})
    r = client.get("/api/chat/lim?limit=3")
    msgs = r.get_json()["messages"]
    assert len(msgs) == 3
    # Oldest-first with limit → last 3 by id
    assert [m["body"] for m in msgs] == ["m7", "m8", "m9"]


def test_clear_room(client):
    for i in range(3):
        client.post("/api/chat/clear-me", json={"username": "u", "body": f"m{i}"})
    r = client.delete("/api/chat/clear-me")
    assert r.get_json()["deleted_count"] == 3
    assert client.get("/api/chat/clear-me").get_json()["messages"] == []


def test_rooms_isolated(client):
    client.post("/api/chat/room-a", json={"username": "u", "body": "in-a"})
    client.post("/api/chat/room-b", json={"username": "u", "body": "in-b"})
    a = client.get("/api/chat/room-a").get_json()["messages"]
    b = client.get("/api/chat/room-b").get_json()["messages"]
    assert len(a) == 1 and a[0]["body"] == "in-a"
    assert len(b) == 1 and b[0]["body"] == "in-b"
