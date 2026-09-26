"""Tests for room read receipts (Phase 47)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_mark_read_requires_auth(client):
    r = client.post("/api/chat/reads-room/read", json={"last_message_id": 1})
    assert r.status_code == 401


def test_mark_read_and_list(client):
    tok = _reg(client, "reads_a")
    client.post("/api/chat/reads-room", json={"username": "reads_a", "body": "hi"})
    r = client.post("/api/chat/reads-room/read", json={"last_message_id": 1},
                    headers=_auth(tok))
    assert r.status_code == 200

    r = client.get("/api/chat/reads-room/reads", headers=_auth(tok))
    assert r.status_code == 200
    reads = r.get_json()["reads"]
    assert len(reads) == 1
    assert reads[0]["username"] == "reads_a"
    assert reads[0]["last_read_message_id"] == 1


def test_mark_read_no_regression(client):
    tok = _reg(client, "reads_b")
    client.post("/api/chat/reads-room2/read", json={"last_message_id": 10},
                headers=_auth(tok))
    r = client.post("/api/chat/reads-room2/read", json={"last_message_id": 5},
                    headers=_auth(tok))
    # No change since we can't go backwards
    assert r.get_json().get("no_change") is True


def test_mark_read_invalid_id(client):
    tok = _reg(client, "reads_c")
    r = client.post("/api/chat/reads-room3/read", json={"last_message_id": -1},
                    headers=_auth(tok))
    assert r.status_code == 400
