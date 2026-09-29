"""Tests for outbound webhooks (Phase 87)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_webhooks_requires_auth(client):
    assert client.get("/api/webhooks").status_code == 401


def test_list_empty(client):
    tok = _reg(client, "wh_a")
    r = client.get("/api/webhooks", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["webhooks"] == []


def test_create_webhook(client):
    tok = _reg(client, "wh_b")
    r = client.post("/api/webhooks", json={
        "url": "https://example.com/hook",
        "events": ["message.created"],
        "description": "test",
    }, headers=_auth(tok))
    assert r.status_code == 201
    body = r.get_json()
    assert body["secret"]
    assert "message.created" in body["events"]


def test_create_invalid_url(client):
    tok = _reg(client, "wh_c")
    r = client.post("/api/webhooks", json={
        "url": "not-a-url", "events": ["message.created"],
    }, headers=_auth(tok))
    assert r.status_code == 400


def test_create_invalid_event(client):
    tok = _reg(client, "wh_d")
    r = client.post("/api/webhooks", json={
        "url": "https://example.com/hook", "events": ["fake.event"],
    }, headers=_auth(tok))
    assert r.status_code == 400


def test_list_hides_secret(client):
    tok = _reg(client, "wh_e")
    client.post("/api/webhooks", json={
        "url": "https://example.com/hook", "events": ["message.created"],
    }, headers=_auth(tok))
    r = client.get("/api/webhooks", headers=_auth(tok))
    wh = r.get_json()["webhooks"][0]
    assert "secret" not in wh
    assert wh["url"] == "https://example.com/hook"


def test_update_webhook(client):
    tok = _reg(client, "wh_f")
    wh = client.post("/api/webhooks", json={
        "url": "https://example.com/a", "events": ["message.created"],
    }, headers=_auth(tok)).get_json()
    r = client.patch(f"/api/webhooks/{wh['id']}",
                     json={"enabled": False}, headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["enabled"] == 0


def test_delete_webhook(client):
    tok = _reg(client, "wh_g")
    wh = client.post("/api/webhooks", json={
        "url": "https://example.com/b", "events": ["message.created"],
    }, headers=_auth(tok)).get_json()
    r = client.delete(f"/api/webhooks/{wh['id']}", headers=_auth(tok))
    assert r.status_code == 200


def test_deliveries_empty(client):
    tok = _reg(client, "wh_h")
    wh = client.post("/api/webhooks", json={
        "url": "https://example.com/c", "events": ["webhook.test"],
    }, headers=_auth(tok)).get_json()
    r = client.get(f"/api/webhooks/{wh['id']}/deliveries", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["deliveries"] == []


def test_cannot_see_others_webhooks(client):
    tok1 = _reg(client, "wh_i1")
    tok2 = _reg(client, "wh_i2")
    wh = client.post("/api/webhooks", json={
        "url": "https://example.com/d", "events": ["message.created"],
    }, headers=_auth(tok1)).get_json()
    r = client.get(f"/api/webhooks/{wh['id']}/deliveries", headers=_auth(tok2))
    assert r.status_code == 404
