"""Tests for group DMs (Phase 56)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_groups_requires_auth(client):
    assert client.get("/api/groups").status_code == 401


def test_create_group(client):
    tok = _reg(client, "grp_a")
    _reg(client, "grp_b")
    _reg(client, "grp_c")

    r = client.post("/api/groups",
                    json={"name": "Team", "usernames": ["grp_b", "grp_c"]},
                    headers=_auth(tok))
    assert r.status_code == 201
    assert r.get_json()["name"] == "Team"
    assert len(r.get_json()["members_added"]) == 2


def test_list_groups(client):
    tok = _reg(client, "grp_a2")
    client.post("/api/groups", json={"name": "G1"}, headers=_auth(tok))
    client.post("/api/groups", json={"name": "G2"}, headers=_auth(tok))
    r = client.get("/api/groups", headers=_auth(tok))
    assert r.status_code == 200
    assert len(r.get_json()["groups"]) == 2


def test_get_group_detail(client):
    tok = _reg(client, "grp_a3")
    gid = client.post("/api/groups", json={"name": "Solo"}, headers=_auth(tok)).get_json()["id"]
    r = client.get(f"/api/groups/{gid}", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["group"]["name"] == "Solo"
    assert len(r.get_json()["members"]) == 1


def test_non_member_cannot_read(client):
    a = _reg(client, "grp_a4")
    b = _reg(client, "grp_b4")
    gid = client.post("/api/groups", json={"name": "Private"}, headers=_auth(a)).get_json()["id"]
    r = client.get(f"/api/groups/{gid}", headers=_auth(b))
    assert r.status_code == 403


def test_send_and_list_messages(client):
    tok = _reg(client, "grp_a5")
    gid = client.post("/api/groups", json={"name": "Chat"}, headers=_auth(tok)).get_json()["id"]

    r = client.post(f"/api/groups/{gid}/messages",
                    json={"body": "hello team", "encrypted": False},
                    headers=_auth(tok))
    assert r.status_code == 201

    r = client.get(f"/api/groups/{gid}/messages", headers=_auth(tok))
    assert len(r.get_json()["messages"]) == 1
    assert r.get_json()["messages"][0]["body"] == "hello team"


def test_add_member(client):
    a = _reg(client, "grp_a6")
    _reg(client, "grp_b6")
    gid = client.post("/api/groups", json={"name": "Add"}, headers=_auth(a)).get_json()["id"]
    r = client.post(f"/api/groups/{gid}/members",
                    json={"username": "grp_b6"}, headers=_auth(a))
    assert r.status_code == 201


def test_remove_self(client):
    a = _reg(client, "grp_a7")
    b = _reg(client, "grp_b7")
    gid = client.post("/api/groups",
                      json={"name": "Leave", "usernames": ["grp_b7"]},
                      headers=_auth(a)).get_json()["id"]
    me_b = client.get("/api/auth/me", headers=_auth(b)).get_json()
    r = client.delete(f"/api/groups/{gid}/members/{me_b['id']}", headers=_auth(b))
    assert r.status_code == 200
