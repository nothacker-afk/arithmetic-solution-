"""Tests for per-action audit retention (Phase 72)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_list_requires_admin(client):
    _reg(client, "ar_admin")
    tok2 = _reg(client, "ar_regular")
    r = client.get("/api/admin/audit_retention", headers=_auth(tok2))
    assert r.status_code == 403


def test_create_policy(client):
    tok = _reg(client, "ar_admin2")
    r = client.post("/api/admin/audit_retention",
                    json={"action_pattern": "auth.*", "retention_days": 30},
                    headers=_auth(tok))
    assert r.status_code == 201
    assert r.get_json()["action_pattern"] == "auth.*"


def test_invalid_pattern(client):
    tok = _reg(client, "ar_admin3")
    for bad in ("", "*foo", "a*b*c", "a b"):
        r = client.post("/api/admin/audit_retention",
                        json={"action_pattern": bad, "retention_days": 30},
                        headers=_auth(tok))
        assert r.status_code == 400, f"expected 400 for pattern {bad!r}"


def test_invalid_days(client):
    tok = _reg(client, "ar_admin4")
    r = client.post("/api/admin/audit_retention",
                    json={"action_pattern": "auth.*", "retention_days": 0},
                    headers=_auth(tok))
    assert r.status_code == 400


def test_upsert_same_pattern(client):
    tok = _reg(client, "ar_admin5")
    client.post("/api/admin/audit_retention",
                json={"action_pattern": "room.*", "retention_days": 30},
                headers=_auth(tok))
    r = client.post("/api/admin/audit_retention",
                    json={"action_pattern": "room.*", "retention_days": 90},
                    headers=_auth(tok))
    assert r.status_code == 201

    r = client.get("/api/admin/audit_retention", headers=_auth(tok))
    policies = r.get_json()["policies"]
    matching = [p for p in policies if p["action_pattern"] == "room.*"]
    assert len(matching) == 1
    assert matching[0]["retention_days"] == 90


def test_delete_policy(client):
    tok = _reg(client, "ar_admin6")
    client.post("/api/admin/audit_retention",
                json={"action_pattern": "x.*", "retention_days": 30},
                headers=_auth(tok))
    pid = client.get("/api/admin/audit_retention", headers=_auth(tok)).get_json()["policies"][0]["id"]
    r = client.delete(f"/api/admin/audit_retention/{pid}", headers=_auth(tok))
    assert r.status_code == 200


def test_preview(client):
    tok = _reg(client, "ar_admin7")
    client.post("/api/admin/audit_retention",
                json={"action_pattern": "auth.*", "retention_days": 30},
                headers=_auth(tok))
    r = client.get("/api/admin/audit_retention/preview", headers=_auth(tok))
    assert r.status_code == 200
    previews = r.get_json()["previews"]
    assert any(p["action_pattern"] == "auth.*" for p in previews)
