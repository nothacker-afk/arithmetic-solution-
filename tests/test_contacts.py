"""Tests for contacts + blocks (Phase 41)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_contacts_requires_auth(client):
    assert client.get("/api/contacts").status_code == 401


def test_add_and_list_contact(client):
    a = _reg(client, "contact_a")
    _reg(client, "contact_b")
    r = client.post("/api/contacts", json={"username": "contact_b"}, headers=_auth(a))
    assert r.status_code == 201

    r = client.get("/api/contacts", headers=_auth(a))
    assert len(r.get_json()["contacts"]) == 1
    assert r.get_json()["contacts"][0]["username"] == "contact_b"


def test_add_self_forbidden(client):
    a = _reg(client, "contact_self")
    r = client.post("/api/contacts", json={"username": "contact_self"}, headers=_auth(a))
    assert r.status_code == 400


def test_add_unknown_user(client):
    a = _reg(client, "contact_a2")
    r = client.post("/api/contacts", json={"username": "nope"}, headers=_auth(a))
    assert r.status_code == 404


def test_favourite_toggle(client):
    a = _reg(client, "contact_a3")
    _reg(client, "contact_b3")
    client.post("/api/contacts", json={"username": "contact_b3"}, headers=_auth(a))
    cid = client.get("/api/contacts", headers=_auth(a)).get_json()["contacts"][0]["contact_user_id"]

    r = client.put(f"/api/contacts/{cid}/favourite",
                   json={"favourite": True}, headers=_auth(a))
    assert r.status_code == 200
    assert r.get_json()["favourite"] == 1

    r = client.get("/api/contacts", headers=_auth(a))
    assert r.get_json()["contacts"][0]["favourite"] == 1


def test_remove_contact(client):
    a = _reg(client, "contact_a4")
    _reg(client, "contact_b4")
    client.post("/api/contacts", json={"username": "contact_b4"}, headers=_auth(a))
    cid = client.get("/api/contacts", headers=_auth(a)).get_json()["contacts"][0]["contact_user_id"]

    r = client.delete(f"/api/contacts/{cid}", headers=_auth(a))
    assert r.status_code == 200
    assert client.get("/api/contacts", headers=_auth(a)).get_json()["contacts"] == []


def test_block_prevents_dm(client):
    a = _reg(client, "block_a")
    b = _reg(client, "block_b")

    # Block first
    r = client.post("/api/blocks", json={"username": "block_b"}, headers=_auth(a))
    assert r.status_code == 201

    # b tries to DM a
    r = client.post("/api/dms/threads", json={"username": "block_a"}, headers=_auth(b))
    assert r.status_code == 403


def test_unblock_allows_dm(client):
    a = _reg(client, "block_a2")
    b = _reg(client, "block_b2")
    client.post("/api/blocks", json={"username": "block_b2"}, headers=_auth(a))
    bid = client.get("/api/blocks", headers=_auth(a)).get_json()["blocks"][0]["blocked_id"]
    client.delete(f"/api/blocks/{bid}", headers=_auth(a))

    r = client.post("/api/dms/threads", json={"username": "block_a2"}, headers=_auth(b))
    assert r.status_code == 201


def test_cannot_block_self(client):
    a = _reg(client, "block_self")
    r = client.post("/api/blocks", json={"username": "block_self"}, headers=_auth(a))
    assert r.status_code == 400
