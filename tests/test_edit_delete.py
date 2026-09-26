"""Tests for message editing + deletion (Phase 38)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_edit_chat_message(client):
    _reg(client, "edit_user1")
    msg = client.post("/api/chat/edit-room", json={
        "username": "edit_user1", "body": "original"}).get_json()

    r = client.patch(f"/api/chat/edit-room/{msg['id']}",
                     json={"body": "updated", "username": "edit_user1"})
    assert r.status_code == 200
    assert r.get_json()["body"] == "updated"
    assert r.get_json()["edited_at"]


def test_edit_wrong_user_forbidden(client):
    _reg(client, "edit_user2")
    msg = client.post("/api/chat/edit-room2", json={
        "username": "edit_user2", "body": "mine"}).get_json()
    r = client.patch(f"/api/chat/edit-room2/{msg['id']}",
                     json={"body": "hacked", "username": "someone_else"})
    assert r.status_code == 403


def test_delete_chat_message(client):
    _reg(client, "del_user1")
    msg = client.post("/api/chat/del-room", json={
        "username": "del_user1", "body": "to be deleted"}).get_json()
    assert msg and msg.get("id"), f"POST failed: {msg}"

    r = client.delete(f"/api/chat/del-room/{msg['id']}?username=del_user1")
    assert r.status_code == 200
    assert r.get_json()["tombstone"] is True

    rows = client.get("/api/chat/del-room").get_json()["messages"]
    tomb = [m for m in rows if m["id"] == msg["id"]][0]
    assert tomb["deleted"] == 1
    assert tomb["body"] == ""


def test_edit_history(client):
    _reg(client, "hist_user1")
    msg = client.post("/api/chat/hist-room", json={
        "username": "hist_user1", "body": "v1"}).get_json()

    r1 = client.patch(f"/api/chat/hist-room/{msg['id']}",
                      json={"body": "v2", "username": "hist_user1"})
    assert r1.status_code == 200, r1.get_json()

    r2 = client.patch(f"/api/chat/hist-room/{msg['id']}",
                      json={"body": "v3", "username": "hist_user1"})
    assert r2.status_code == 200, r2.get_json()

    r = client.get(f"/api/chat/hist-room/{msg['id']}/edits")
    assert r.status_code == 200
    edits = r.get_json()["edits"]
    assert len(edits) == 2, f"expected 2 edits, got {len(edits)}: {edits}"
    assert edits[-1]["old_body"] == "v1"
    assert edits[0]["old_body"] == "v2"


def test_delete_dm(client):
    a = _reg(client, "dm_del_a")
    _reg(client, "dm_del_b")
    tid = client.post("/api/dms/threads", json={"username": "dm_del_b"},
                      headers=_auth(a)).get_json()["thread_id"]
    msg = client.post(f"/api/dms/threads/{tid}", json={"body": "hi"},
                      headers=_auth(a)).get_json()

    r = client.delete(f"/api/dms/threads/{tid}/messages/{msg['id']}",
                      headers=_auth(a))
    assert r.status_code == 200
    assert r.get_json()["tombstone"] is True
