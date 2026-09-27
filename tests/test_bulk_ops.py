"""Tests for bulk message ops (Phase 74)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_bulk_delete_own_messages(client):
    tok = _reg(client, "bulk_a")
    ids = []
    for i in range(3):
        m = client.post("/api/chat/bulk-room",
                        json={"username": "bulk_a", "body": f"m{i}"}).get_json()
        ids.append(m["id"])

    r = client.post("/api/rooms/bulk-room/messages/bulk",
                    json={"action": "delete", "message_ids": ids},
                    headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["affected"] == 3


def test_bulk_delete_others_forbidden(client):
    tok_a = _reg(client, "bulk_b1")
    tok_b = _reg(client, "bulk_b2")
    m = client.post("/api/chat/bulk-room2",
                    json={"username": "bulk_b1", "body": "mine"}).get_json()
    r = client.post("/api/rooms/bulk-room2/messages/bulk",
                    json={"action": "delete", "message_ids": [m["id"]]},
                    headers=_auth(tok_b))
    assert r.status_code == 403


def test_bulk_restore(client):
    tok = _reg(client, "bulk_c")
    m = client.post("/api/chat/bulk-room3",
                    json={"username": "bulk_c", "body": "hi"}).get_json()
    client.post("/api/rooms/bulk-room3/messages/bulk",
                json={"action": "delete", "message_ids": [m["id"]]},
                headers=_auth(tok))
    r = client.post("/api/rooms/bulk-room3/messages/bulk",
                    json={"action": "restore", "message_ids": [m["id"]]},
                    headers=_auth(tok))
    assert r.get_json()["affected"] == 1


def test_bulk_invalid_action(client):
    tok = _reg(client, "bulk_d")
    r = client.post("/api/rooms/bulk-room4/messages/bulk",
                    json={"action": "nuke", "message_ids": [1]},
                    headers=_auth(tok))
    assert r.status_code == 400


def test_bulk_max_ids(client):
    tok = _reg(client, "bulk_e")
    r = client.post("/api/rooms/bulk-room5/messages/bulk",
                    json={"action": "delete", "message_ids": list(range(1, 300))},
                    headers=_auth(tok))
    assert r.status_code == 400


def test_bulk_operation_logged(client):
    tok = _reg(client, "bulk_f")
    m = client.post("/api/chat/bulk-room6",
                    json={"username": "bulk_f", "body": "x"}).get_json()
    client.post("/api/rooms/bulk-room6/messages/bulk",
                json={"action": "delete", "message_ids": [m["id"]]},
                headers=_auth(tok))
    # bulk_f is owner of their own room so can list ops
    client.post("/api/rooms/bulk-room6/claim", json={}, headers=_auth(tok))
    r = client.get("/api/rooms/bulk-room6/bulk_operations", headers=_auth(tok))
    assert r.status_code == 200
