"""Tests for email digests (Phase 75)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_default_subscription(client):
    tok = _reg(client, "dig_a")
    r = client.get("/api/digest/subscription", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["frequency"] == "weekly"
    assert r.get_json()["enabled"] is False


def test_set_subscription(client):
    tok = _reg(client, "dig_b")
    r = client.put("/api/digest/subscription",
                   json={"frequency": "daily", "enabled": True},
                   headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["frequency"] == "daily"

    r = client.get("/api/digest/subscription", headers=_auth(tok))
    assert r.get_json()["enabled"] is True


def test_invalid_frequency(client):
    tok = _reg(client, "dig_c")
    r = client.put("/api/digest/subscription",
                   json={"frequency": "hourly", "enabled": True},
                   headers=_auth(tok))
    assert r.status_code == 400


def test_test_endpoint_reports_unconfigured(client, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    tok = _reg(client, "dig_d")
    r = client.post("/api/digest/test", headers=_auth(tok))
    assert r.status_code == 503
    assert "not configured" in r.get_json()["error"].lower()


def test_tick_skips_when_unconfigured(monkeypatch):
    from web.backend import digests
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert digests.tick() == 0
