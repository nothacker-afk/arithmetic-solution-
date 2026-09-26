"""Tests for export (Phase 34)."""
import json


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def test_export_room_requires_auth(client):
    assert client.get("/api/export/room/test").status_code == 401


def test_export_room_json(client):
    tok = _reg(client, "export_user1")
    client.post("/api/chat/exp-room", json={"username": "export_user1", "body": "hello"})
    client.post("/api/chat/exp-room", json={"username": "export_user1", "body": "world"})

    r = client.get("/api/export/room/exp-room?format=json", headers=_auth(tok))
    assert r.status_code == 200
    assert "attachment" in r.headers["Content-Disposition"]
    data = json.loads(r.data)
    assert len(data["messages"]) == 2


def test_export_room_markdown(client):
    tok = _reg(client, "export_user2")
    client.post("/api/chat/exp-room2", json={"username": "export_user2", "body": "hello"})
    r = client.get("/api/export/room/exp-room2?format=md", headers=_auth(tok))
    assert r.status_code == 200
    assert b"# Chat export" in r.data
    assert b"hello" in r.data


def test_export_room_html(client):
    tok = _reg(client, "export_user3")
    client.post("/api/chat/exp-room3", json={"username": "export_user3", "body": "hi"})
    r = client.get("/api/export/room/exp-room3?format=html", headers=_auth(tok))
    assert r.status_code == 200
    assert b"Print" in r.data
    assert b"window.print()" in r.data


def test_export_invalid_format(client):
    tok = _reg(client, "export_user4")
    r = client.get("/api/export/room/any?format=xml", headers=_auth(tok))
    assert r.status_code == 400


def test_export_dm_thread(client):
    t1 = _reg(client, "export_dm_a")
    _t2 = _reg(client, "export_dm_b")
    thread_id = client.post("/api/dms/threads", json={"username": "export_dm_b"},
                            headers=_auth(t1)).get_json()["thread_id"]
    client.post(f"/api/dms/threads/{thread_id}",
                json={"body": "cipher", "encrypted": True}, headers=_auth(t1))

    r = client.get(f"/api/export/dm/{thread_id}?format=md", headers=_auth(t1))
    assert r.status_code == 200
    assert b"DM export" in r.data


def test_export_dm_third_party_denied(client):
    t1 = _reg(client, "export_x")
    _t2 = _reg(client, "export_y")
    t3 = _reg(client, "export_z")
    thread_id = client.post("/api/dms/threads", json={"username": "export_y"},
                            headers=_auth(t1)).get_json()["thread_id"]
    r = client.get(f"/api/export/dm/{thread_id}?format=md", headers=_auth(t3))
    assert r.status_code == 404
