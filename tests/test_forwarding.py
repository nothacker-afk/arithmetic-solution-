"""Tests for message forwarding (Phase 86)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_forward_requires_auth(client):
    r = client.post("/api/forward", json={})
    assert r.status_code == 401


def test_forward_chat_to_chat(client):
    tok = _reg(client, "fwd_a")
    msg = client.post("/api/chat/fwd-src", json={
        "username": "fwd_a", "body": "original message"}).get_json()
    r = client.post("/api/forward", json={
        "source_kind": "chat", "source_id": msg["id"],
        "dest_kind": "chat", "dest_id": "fwd-dst",
    }, headers=_auth(tok))
    assert r.status_code == 201
    new_id = r.get_json()["new_message_id"]

    # Verify the forwarded message landed in the destination
    rows = client.get("/api/chat/fwd-dst").get_json()["messages"]
    fwd = [m for m in rows if m["id"] == new_id]
    assert fwd
    assert "Forwarded from" in fwd[0]["body"]
    assert "original message" in fwd[0]["body"]


def test_forward_missing_source(client):
    tok = _reg(client, "fwd_b")
    r = client.post("/api/forward", json={
        "source_kind": "chat", "source_id": 99999,
        "dest_kind": "chat", "dest_id": "any",
    }, headers=_auth(tok))
    assert r.status_code == 403


def test_forward_invalid_kind(client):
    tok = _reg(client, "fwd_c")
    r = client.post("/api/forward", json={
        "source_kind": "nope", "source_id": 1,
        "dest_kind": "chat", "dest_id": "x",
    }, headers=_auth(tok))
    assert r.status_code == 400


def test_forward_history(client):
    tok = _reg(client, "fwd_d")
    msg = client.post("/api/chat/fwd-src2", json={
        "username": "fwd_d", "body": "y"}).get_json()
    client.post("/api/forward", json={
        "source_kind": "chat", "source_id": msg["id"],
        "dest_kind": "chat", "dest_id": "fwd-dst2",
    }, headers=_auth(tok))
    r = client.get("/api/forward/history", headers=_auth(tok))
    assert r.status_code == 200
    assert len(r.get_json()["forwards"]) >= 1
