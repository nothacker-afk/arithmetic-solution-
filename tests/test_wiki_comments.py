"""Tests for wiki comments (Phase 68)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _make_page(client, tok, room="wc-room"):
    return client.post(f"/api/rooms/{room}/wiki",
                       json={"title": "Discussion", "body": "hi"},
                       headers=_auth(tok)).get_json()["id"]


def test_list_comments_empty(client):
    tok = _reg(client, "wc_a")
    pid = _make_page(client, tok)
    r = client.get(f"/api/wiki/{pid}/comments", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["comments"] == []


def test_add_comment(client):
    tok = _reg(client, "wc_b")
    pid = _make_page(client, tok)
    r = client.post(f"/api/wiki/{pid}/comments",
                    json={"body": "First!"}, headers=_auth(tok))
    assert r.status_code == 201
    assert r.get_json()["body"] == "First!"


def test_reply_to_comment(client):
    tok = _reg(client, "wc_c")
    pid = _make_page(client, tok)
    parent = client.post(f"/api/wiki/{pid}/comments",
                         json={"body": "top"}, headers=_auth(tok)).get_json()

    r = client.post(f"/api/wiki/{pid}/comments",
                    json={"body": "reply", "parent_id": parent["id"]},
                    headers=_auth(tok))
    assert r.status_code == 201

    r = client.get(f"/api/wiki/{pid}/comments", headers=_auth(tok))
    comments = r.get_json()["comments"]
    assert len(comments) == 1
    assert len(comments[0]["replies"]) == 1


def test_edit_comment(client):
    tok = _reg(client, "wc_d")
    pid = _make_page(client, tok)
    c = client.post(f"/api/wiki/{pid}/comments",
                    json={"body": "original"}, headers=_auth(tok)).get_json()
    r = client.patch(f"/api/wiki/{pid}/comments/{c['id']}",
                     json={"body": "edited"}, headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["body"] == "edited"


def test_cannot_edit_others_comment(client):
    tok_a = _reg(client, "wc_e1")
    tok_b = _reg(client, "wc_e2")
    pid = _make_page(client, tok_a)
    c = client.post(f"/api/wiki/{pid}/comments",
                    json={"body": "mine"}, headers=_auth(tok_a)).get_json()
    r = client.patch(f"/api/wiki/{pid}/comments/{c['id']}",
                     json={"body": "hacked"}, headers=_auth(tok_b))
    assert r.status_code == 403


def test_delete_comment_tombstone(client):
    tok = _reg(client, "wc_f")
    pid = _make_page(client, tok)
    c = client.post(f"/api/wiki/{pid}/comments",
                    json={"body": "bye"}, headers=_auth(tok)).get_json()
    r = client.delete(f"/api/wiki/{pid}/comments/{c['id']}", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["tombstone"] is True


def test_comment_on_missing_page(client):
    tok = _reg(client, "wc_g")
    r = client.get("/api/wiki/" + "0" * 32 + "/comments", headers=_auth(tok))
    assert r.status_code == 404


def test_invalid_parent(client):
    tok = _reg(client, "wc_h")
    pid = _make_page(client, tok)
    r = client.post(f"/api/wiki/{pid}/comments",
                    json={"body": "x", "parent_id": 99999}, headers=_auth(tok))
    assert r.status_code == 404
