"""Tests for threaded DM replies (Phase 82)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_thread_requires_participant(client):
    a = _reg(client, "dt_a")
    b = _reg(client, "dt_b")
    c = _reg(client, "dt_c")
    tid = client.post("/api/dms/threads", json={"username": "dt_b"},
                      headers=_auth(a)).get_json()["thread_id"]
    msg = client.post(f"/api/dms/threads/{tid}", json={"body": "hi"},
                      headers=_auth(a)).get_json()
    r = client.get(f"/api/dms/threads/{tid}/messages/{msg['id']}/thread",
                   headers=_auth(c))
    assert r.status_code == 403


def test_thread_overview_empty(client):
    a = _reg(client, "dt_a2")
    _reg(client, "dt_b2")
    tid = client.post("/api/dms/threads", json={"username": "dt_b2"},
                      headers=_auth(a)).get_json()["thread_id"]
    msg = client.post(f"/api/dms/threads/{tid}", json={"body": "root"},
                      headers=_auth(a)).get_json()
    r = client.get(f"/api/dms/threads/{tid}/messages/{msg['id']}/thread",
                   headers=_auth(a))
    assert r.status_code == 200
    data = r.get_json()
    assert data["parent"]["id"] == msg["id"]
    assert data["parent"]["reply_count"] == 0
    assert data["replies"] == []


def test_thread_missing_parent(client):
    a = _reg(client, "dt_a3")
    _reg(client, "dt_b3")
    tid = client.post("/api/dms/threads", json={"username": "dt_b3"},
                      headers=_auth(a)).get_json()["thread_id"]
    r = client.get(f"/api/dms/threads/{tid}/messages/99999/thread",
                   headers=_auth(a))
    assert r.status_code == 404


def test_replies_endpoint(client):
    a = _reg(client, "dt_a4")
    _reg(client, "dt_b4")
    tid = client.post("/api/dms/threads", json={"username": "dt_b4"},
                      headers=_auth(a)).get_json()["thread_id"]
    parent = client.post(f"/api/dms/threads/{tid}", json={"body": "root"},
                         headers=_auth(a)).get_json()

    # Insert a reply directly (POST endpoint accepts parent_id in Phase 82+)
    from web.backend.database import get_db
    with get_db() as conn:
        conn.execute(
            "INSERT INTO dm_messages (thread_id, sender_id, body, parent_id) "
            "VALUES (?, 1, 'reply', ?)", (tid, parent["id"])
        )

    r = client.get(f"/api/dms/threads/{tid}/messages/{parent['id']}/replies",
                   headers=_auth(a))
    assert r.status_code == 200
    assert len(r.get_json()["replies"]) == 1
