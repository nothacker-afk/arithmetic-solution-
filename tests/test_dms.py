"""Tests for encrypted DMs (Phase 30)."""
import base64
import pytest


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _register(client, username):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secret123",
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"], r.get_json()["user_id"]


def test_list_threads_requires_auth(client):
    assert client.get("/api/dms/threads").status_code == 401


def test_start_thread_requires_auth(client):
    assert client.post("/api/dms/threads", json={"username": "x"}).status_code == 401


def test_start_thread_unknown_user(client):
    tok, _ = _register(client, "dm_alice1")
    r = client.post("/api/dms/threads", json={"username": "nonexistent"},
                    headers=_auth(tok))
    assert r.status_code == 404


def test_start_thread_self_forbidden(client):
    tok, _ = _register(client, "dm_solo")
    r = client.post("/api/dms/threads", json={"username": "dm_solo"},
                    headers=_auth(tok))
    assert r.status_code == 400


def test_full_dm_flow(client):
    alice_tok, _ = _register(client, "dm_alice")
    bob_tok, _ = _register(client, "dm_bob")

    # Alice starts a thread
    r = client.post("/api/dms/threads", json={"username": "dm_bob"},
                    headers=_auth(alice_tok))
    assert r.status_code == 201
    thread_id = r.get_json()["thread_id"]

    # Alice sends a message (ciphertext)
    ct = base64.b64encode(b"fake-ciphertext-here").decode()
    r = client.post(f"/api/dms/threads/{thread_id}",
                    json={"body": ct, "encrypted": True},
                    headers=_auth(alice_tok))
    assert r.status_code == 201
    assert r.get_json()["sender"] == "dm_alice"

    # Bob fetches the thread
    r = client.get(f"/api/dms/threads/{thread_id}", headers=_auth(bob_tok))
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["messages"]) == 1
    assert data["messages"][0]["body"] == ct
    assert data["participants"]["me"] == "dm_bob"
    assert data["participants"]["other"] == "dm_alice"


def test_threads_listed_for_both(client):
    a_tok, _ = _register(client, "dm_c")
    b_tok, _ = _register(client, "dm_d")
    client.post("/api/dms/threads", json={"username": "dm_d"}, headers=_auth(a_tok))

    for tok in (a_tok, b_tok):
        r = client.get("/api/dms/threads", headers=_auth(tok))
        assert len(r.get_json()["threads"]) == 1


def test_third_party_cannot_read(client):
    a_tok, _ = _register(client, "dm_e")
    b_tok, _ = _register(client, "dm_f")
    c_tok, _ = _register(client, "dm_g")

    thread_id = client.post("/api/dms/threads", json={"username": "dm_f"},
                            headers=_auth(a_tok)).get_json()["thread_id"]

    r = client.get(f"/api/dms/threads/{thread_id}", headers=_auth(c_tok))
    assert r.status_code == 403

    r = client.post(f"/api/dms/threads/{thread_id}",
                    json={"body": "sneak"}, headers=_auth(c_tok))
    assert r.status_code == 403


def test_thread_idempotent(client):
    a_tok, _ = _register(client, "dm_h")
    b_tok, _ = _register(client, "dm_i")
    id1 = client.post("/api/dms/threads", json={"username": "dm_i"},
                      headers=_auth(a_tok)).get_json()["thread_id"]
    id2 = client.post("/api/dms/threads", json={"username": "dm_i"},
                      headers=_auth(a_tok)).get_json()["thread_id"]
    assert id1 == id2

    # From the other side, same thread
    id3 = client.post("/api/dms/threads", json={"username": "dm_h"},
                      headers=_auth(b_tok)).get_json()["thread_id"]
    assert id3 == id1


def test_empty_body_rejected(client):
    a_tok, _ = _register(client, "dm_j")
    _b_tok, _ = _register(client, "dm_k")
    thread_id = client.post("/api/dms/threads", json={"username": "dm_k"},
                            headers=_auth(a_tok)).get_json()["thread_id"]
    r = client.post(f"/api/dms/threads/{thread_id}", json={"body": ""},
                    headers=_auth(a_tok))
    assert r.status_code == 400


def test_body_too_long(client):
    a_tok, _ = _register(client, "dm_l")
    _b_tok, _ = _register(client, "dm_m")
    thread_id = client.post("/api/dms/threads", json={"username": "dm_m"},
                            headers=_auth(a_tok)).get_json()["thread_id"]
    r = client.post(f"/api/dms/threads/{thread_id}",
                    json={"body": "x" * 10000}, headers=_auth(a_tok))
    assert r.status_code == 400


def test_delete_thread(client):
    a_tok, _ = _register(client, "dm_n")
    _b_tok, _ = _register(client, "dm_o")
    thread_id = client.post("/api/dms/threads", json={"username": "dm_o"},
                            headers=_auth(a_tok)).get_json()["thread_id"]
    r = client.delete(f"/api/dms/threads/{thread_id}", headers=_auth(a_tok))
    assert r.status_code == 200
    r = client.get(f"/api/dms/threads/{thread_id}", headers=_auth(a_tok))
    assert r.status_code == 404


def test_unread_count(client):
    a_tok, _ = _register(client, "dm_p")
    b_tok, _ = _register(client, "dm_q")
    thread_id = client.post("/api/dms/threads", json={"username": "dm_q"},
                            headers=_auth(a_tok)).get_json()["thread_id"]

    # Alice sends two messages
    for _ in range(2):
        client.post(f"/api/dms/threads/{thread_id}",
                    json={"body": "x"}, headers=_auth(a_tok))

    # Bob sees 2 unread
    r = client.get("/api/dms/threads", headers=_auth(b_tok))
    thread = r.get_json()["threads"][0]
    assert thread["unread"] == 2

    # Bob reads them
    client.get(f"/api/dms/threads/{thread_id}", headers=_auth(b_tok))

    # Now 0 unread
    r = client.get("/api/dms/threads", headers=_auth(b_tok))
    thread = r.get_json()["threads"][0]
    assert thread["unread"] == 0
