"""Tests for message editing + deletion (Phase 38)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_edit_chat_message(client):
    _reg(client, "edit_user1")
    msg = client.post("/api/chat/edit-room", json={
        "username": "edit_user1", "body": "original"}).get_json()

    r = client.request("/api/chat/edit-room/" + str(msg["id"]),
                       method="PATCH",
                       json={"body": "updated", "username": "edit_user1"})
    assert r.status_code == 200
    assert r.get_json()["body"] == "updated"
    assert r.get_json()["edited_at"]


def test_edit_wrong_user_forbidden(client):
    _reg(client, "edit_user2")
    msg = client.post("/api/chat/edit-room2", json={
        "username": "edit_user2", "body": "mine"}).get_json()
    r = client.request("/api/chat/edit-room2/" + str(msg["id"]),
                       method="PATCH",
                       json={"body": "hacked", "username": "someone_else"})
    assert r.status_code == 403


def test_delete_chat_message(client):
    _reg(client, "del_user1")
    msg = client.post("/api/chat/del-room", json={
        "username": "del_user1", "body": "to be deleted"}).get_json()

    r = client.request(
        f"/api/chat/del-room/{msg['id']}?username=del_user1",
        method="DELETE")
    assert r.status_code == 200
    assert r.get_json()["tombstone"] is True

    # Verify tombstone state
    rows = client.get("/api/chat/del-room").get_json()["messages"]
    tomb = [m for m in rows if m["id"] == msg["id"]][0]
    assert tomb["deleted"] == 1
    assert tomb["body"] == ""


def test_edit_history(client):
    _reg(client, "hist_user1")
    msg = client.post("/api/chat/hist-room", json={
        "username": "hist_user1", "body": "v1"}).get_json()

    client.request(f"/api/chat/hist-room/{msg['id']}", method="PATCH",
                   json={"body": "v2", "username": "hist_user1"})
    client.request(f"/api/chat/hist-room/{msg['id']}", method="PATCH",
                   json={"body": "v3", "username": "hist_user1"})

    r = client.get(f"/api/chat/hist-room/{msg['id']}/edits")
    assert r.status_code == 200
    edits = r.get_json()["edits"]
    assert len(edits) == 2
    assert edits[-1]["old_body"] == "v1"
    assert edits[0]["old_body"] == "v2"


def test_delete_dm(client):
    a, _ = _reg(client, "dm_del_a")
    b, _ = _reg(client, "dm_del_b")
    tid = client.post("/api/dms/threads", json={"username": "dm_del_b"},
                      headers=_auth(a)).get_json()["thread_id"]
    msg = client.post(f"/api/dms/threads/{tid}", json={"body": "hi"},
                      headers=_auth(a)).get_json()

    r = client.delete(
        f"/api/dms/threads/{tid}/messages/{msg['id']}",
        headers=_auth(a))
    assert r.status_code == 200
    assert r.get_json()["tombstone"] is True
