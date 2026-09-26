"""Tests for group message threads (Phase 62)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_reply_creates_threaded_message(client):
    tok = _reg(client, "grt_a")
    gid = client.post("/api/groups", json={"name": "Team"},
                      headers=_auth(tok)).get_json()["id"]

    parent = client.post(f"/api/groups/{gid}/messages",
                         json={"body": "root", "encrypted": False},
                         headers=_auth(tok)).get_json()

    # Direct insert of a reply requires parent_id support in the messages route;
    # the endpoint as written doesn't yet accept parent_id, so we test the
    # read-side thread endpoints by backfilling via SQL
    from web.backend.database import get_db
    with get_db() as conn:
        conn.execute(
            "INSERT INTO group_messages (group_id, sender_id, body, parent_id) "
            "VALUES (?, 1, 'reply', ?)", (gid, parent["id"]),
        )

    r = client.get(f"/api/groups/{gid}/messages/{parent['id']}/replies",
                   headers=_auth(tok))
    assert r.status_code == 200
    assert len(r.get_json()["replies"]) == 1


def test_thread_overview(client):
    tok = _reg(client, "grt_b")
    gid = client.post("/api/groups", json={"name": "Team"},
                      headers=_auth(tok)).get_json()["id"]

    parent = client.post(f"/api/groups/{gid}/messages",
                         json={"body": "root", "encrypted": False},
                         headers=_auth(tok)).get_json()

    r = client.get(f"/api/groups/{gid}/messages/{parent['id']}/thread",
                   headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["parent"]["id"] == parent["id"]
    assert r.get_json()["parent"]["reply_count"] == 0


def test_replies_requires_membership(client):
    tok_a = _reg(client, "grt_c1")
    tok_b = _reg(client, "grt_c2")
    gid = client.post("/api/groups", json={"name": "Private"},
                      headers=_auth(tok_a)).get_json()["id"]
    parent = client.post(f"/api/groups/{gid}/messages",
                         json={"body": "x", "encrypted": False},
                         headers=_auth(tok_a)).get_json()
    r = client.get(f"/api/groups/{gid}/messages/{parent['id']}/replies",
                   headers=_auth(tok_b))
    assert r.status_code == 403


def test_thread_missing_parent(client):
    tok = _reg(client, "grt_d")
    gid = client.post("/api/groups", json={"name": "T"},
                      headers=_auth(tok)).get_json()["id"]
    r = client.get(f"/api/groups/{gid}/messages/99999/thread", headers=_auth(tok))
    assert r.status_code == 404
