"""Tests for group E2E encryption (Phase 70)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_get_encryption_requires_membership(client):
    tok_a = _reg(client, "ge_a")
    tok_b = _reg(client, "ge_b")
    gid = client.post("/api/groups", json={"name": "G"}, headers=_auth(tok_a)).get_json()["id"]
    r = client.get(f"/api/groups/{gid}/encryption", headers=_auth(tok_b))
    assert r.status_code == 403


def test_get_encryption_creates_salt(client):
    tok = _reg(client, "ge_c")
    gid = client.post("/api/groups", json={"name": "G"}, headers=_auth(tok)).get_json()["id"]
    r = client.get(f"/api/groups/{gid}/encryption", headers=_auth(tok))
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["salt"]) == 32  # 16 bytes hex
    assert data["key_version"] == 1


def test_salt_is_stable(client):
    tok = _reg(client, "ge_d")
    gid = client.post("/api/groups", json={"name": "G"}, headers=_auth(tok)).get_json()["id"]
    a = client.get(f"/api/groups/{gid}/encryption", headers=_auth(tok)).get_json()
    b = client.get(f"/api/groups/{gid}/encryption", headers=_auth(tok)).get_json()
    assert a["salt"] == b["salt"]


def test_rotate_requires_owner(client):
    tok_a = _reg(client, "ge_e1")
    tok_b = _reg(client, "ge_e2")
    gid = client.post("/api/groups",
                      json={"name": "G", "usernames": ["ge_e2"]},
                      headers=_auth(tok_a)).get_json()["id"]
    # Ensure member is not owner
    r = client.post(f"/api/groups/{gid}/encryption/rotate", headers=_auth(tok_b))
    assert r.status_code == 403


def test_rotate_changes_salt(client):
    tok = _reg(client, "ge_f")
    gid = client.post("/api/groups", json={"name": "G"}, headers=_auth(tok)).get_json()["id"]
    before = client.get(f"/api/groups/{gid}/encryption", headers=_auth(tok)).get_json()
    after = client.post(f"/api/groups/{gid}/encryption/rotate",
                        headers=_auth(tok)).get_json()
    assert after["salt"] != before["salt"]
    assert after["key_version"] == 2
