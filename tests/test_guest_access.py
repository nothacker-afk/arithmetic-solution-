"""Tests for guest access links (Phase 65)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_create_requires_owner(client):
    a = _reg(client, "ga_a")
    b = _reg(client, "ga_b")
    client.post("/api/rooms/ga-room/claim", json={}, headers=_auth(a))
    r = client.post("/api/rooms/ga-room/guest_tokens", json={}, headers=_auth(b))
    assert r.status_code == 403


def test_create_and_redeem(client):
    a = _reg(client, "ga_c")
    client.post("/api/rooms/ga-room2/claim", json={}, headers=_auth(a))
    r = client.post("/api/rooms/ga-room2/guest_tokens",
                    json={"label": "friend", "max_uses": 1},
                    headers=_auth(a))
    assert r.status_code == 201
    token = r.get_json()["token"]

    # Inspect
    r = client.get(f"/api/guest/{token}")
    assert r.status_code == 200
    assert r.get_json()["room"] == "ga-room2"

    # Redeem
    r = client.post(f"/api/guest/{token}/redeem")
    assert r.status_code == 200
    assert r.get_json()["uses_remaining"] == 0

    # Second redeem fails
    r = client.post(f"/api/guest/{token}/redeem")
    assert r.status_code == 410


def test_revoke(client):
    a = _reg(client, "ga_d")
    client.post("/api/rooms/ga-room3/claim", json={}, headers=_auth(a))
    tok = client.post("/api/rooms/ga-room3/guest_tokens", json={},
                      headers=_auth(a)).get_json()["token"]
    r = client.delete(f"/api/guest_tokens/{tok}", headers=_auth(a))
    assert r.status_code == 200
    r = client.get(f"/api/guest/{tok}")
    assert r.status_code == 404


def test_invalid_token(client):
    r = client.get("/api/guest/not-a-real-token")
    assert r.status_code == 404


def test_list_tokens_hides_full(client):
    a = _reg(client, "ga_e")
    client.post("/api/rooms/ga-room4/claim", json={}, headers=_auth(a))
    client.post("/api/rooms/ga-room4/guest_tokens", json={}, headers=_auth(a))
    r = client.get("/api/rooms/ga-room4/guest_tokens", headers=_auth(a))
    tokens = r.get_json()["tokens"]
    assert len(tokens) == 1
    assert "token" not in tokens[0]
    assert tokens[0].get("token_prefix", "").endswith("…")
