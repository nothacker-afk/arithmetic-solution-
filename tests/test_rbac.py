"""Tests for advanced RBAC (Phase 76)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_available_permissions(client):
    r = client.get("/api/rooms/permissions/available")
    assert r.status_code == 200
    perms = r.get_json()["permissions"]
    for p in ("can_post", "can_pin", "can_kick", "can_manage_roles"):
        assert p in perms


def test_owner_gets_all_permissions(client):
    tok = _reg(client, "rb_a")
    client.post("/api/rooms/rb-room/claim", json={}, headers=_auth(tok))
    r = client.get("/api/rooms/rb-room/roles", headers=_auth(tok))
    data = r.get_json()
    assert data["is_owner"] is True
    assert all(data["my_permissions"].values())


def test_non_member_has_none(client):
    tok = _reg(client, "rb_b")
    r = client.get("/api/rooms/rb-missing/permissions/rb_b", headers=_auth(tok))
    assert r.status_code == 200
    assert all(not v for v in r.get_json()["permissions"].values())


def test_create_role(client):
    tok = _reg(client, "rb_c")
    client.post("/api/rooms/rb-room2/claim", json={}, headers=_auth(tok))
    r = client.post("/api/rooms/rb-room2/roles",
                    json={"name": "moderator",
                          "permissions": ["can_pin", "can_kick"]},
                    headers=_auth(tok))
    assert r.status_code == 201

    r = client.get("/api/rooms/rb-room2/roles", headers=_auth(tok))
    roles = r.get_json()["roles"]
    assert any(role["name"] == "moderator" for role in roles)


def test_invalid_permission(client):
    tok = _reg(client, "rb_d")
    client.post("/api/rooms/rb-room3/claim", json={}, headers=_auth(tok))
    r = client.post("/api/rooms/rb-room3/roles",
                    json={"name": "fake", "permissions": ["can_fly"]},
                    headers=_auth(tok))
    assert r.status_code == 400


def test_assign_role(client):
    tok_a = _reg(client, "rb_e1")
    tok_b = _reg(client, "rb_e2")
    client.post("/api/rooms/rb-room4/claim", json={}, headers=_auth(tok_a))
    # Invite b and add to room
    inv = client.post("/api/rooms/rb-room4/invites", json={},
                      headers=_auth(tok_a)).get_json()
    client.post("/api/rooms/rb-room4/join",
                json={"invite": inv["token"]}, headers=_auth(tok_b))
    # Create role + assign
    client.post("/api/rooms/rb-room4/roles",
                json={"name": "helper", "permissions": ["can_pin"]},
                headers=_auth(tok_a))
    r = client.post("/api/rooms/rb-room4/roles/helper/assign",
                    json={"username": "rb_e2"}, headers=_auth(tok_a))
    assert r.status_code == 201

    # Verify: b now has can_pin
    r = client.get("/api/rooms/rb-room4/permissions/rb_e2", headers=_auth(tok_a))
    assert r.get_json()["permissions"]["can_pin"] is True
    assert r.get_json()["permissions"]["can_kick"] is False


def test_non_member_cannot_get_role(client):
    tok_a = _reg(client, "rb_f1")
    tok_b = _reg(client, "rb_f2")
    client.post("/api/rooms/rb-room5/claim", json={}, headers=_auth(tok_a))
    client.post("/api/rooms/rb-room5/roles",
                json={"name": "mod", "permissions": ["can_pin"]},
                headers=_auth(tok_a))
    r = client.post("/api/rooms/rb-room5/roles/mod/assign",
                    json={"username": "rb_f2"}, headers=_auth(tok_a))
    assert r.status_code == 400


def test_delete_role(client):
    tok = _reg(client, "rb_g")
    client.post("/api/rooms/rb-room6/claim", json={}, headers=_auth(tok))
    client.post("/api/rooms/rb-room6/roles",
                json={"name": "temp", "permissions": []},
                headers=_auth(tok))
    r = client.delete("/api/rooms/rb-room6/roles/temp", headers=_auth(tok))
    assert r.status_code == 200
