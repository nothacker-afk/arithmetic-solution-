"""Tests for room themes (Phase 81)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_default_theme(client):
    tok = _reg(client, "theme_a")
    r = client.get("/api/rooms/theme-room/theme", headers=_auth(tok))
    assert r.status_code == 200
    body = r.get_json()
    assert body["is_custom"] is False
    assert body["accent"] is None


def test_set_theme_requires_owner(client):
    tok_a = _reg(client, "theme_b1")
    tok_b = _reg(client, "theme_b2")
    client.post("/api/rooms/theme-room2/claim", json={}, headers=_auth(tok_a))
    r = client.put("/api/rooms/theme-room2/theme",
                   json={"accent": "#ff0000"}, headers=_auth(tok_b))
    assert r.status_code == 403


def test_set_and_get_theme(client):
    tok = _reg(client, "theme_c")
    client.post("/api/rooms/theme-room3/claim", json={}, headers=_auth(tok))
    r = client.put("/api/rooms/theme-room3/theme",
                   json={"accent": "#38bdf8", "accent_2": "#818cf8",
                         "emoji": "🚀", "banner_url": "https://example.com/banner.png"},
                   headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["accent"] == "#38bdf8"
    assert r.get_json()["emoji"] == "🚀"

    r = client.get("/api/rooms/theme-room3/theme", headers=_auth(tok))
    body = r.get_json()
    assert body["accent"] == "#38bdf8"
    assert body["is_custom"] is True


def test_invalid_color(client):
    tok = _reg(client, "theme_d")
    client.post("/api/rooms/theme-room4/claim", json={}, headers=_auth(tok))
    r = client.put("/api/rooms/theme-room4/theme",
                   json={"accent": "not-a-color"}, headers=_auth(tok))
    assert r.status_code == 400


def test_invalid_banner_url(client):
    tok = _reg(client, "theme_e")
    client.post("/api/rooms/theme-room5/claim", json={}, headers=_auth(tok))
    r = client.put("/api/rooms/theme-room5/theme",
                   json={"banner_url": "ftp://nope"}, headers=_auth(tok))
    assert r.status_code == 400


def test_reset_theme(client):
    tok = _reg(client, "theme_f")
    client.post("/api/rooms/theme-room6/claim", json={}, headers=_auth(tok))
    client.put("/api/rooms/theme-room6/theme",
               json={"accent": "#ff0000"}, headers=_auth(tok))
    r = client.delete("/api/rooms/theme-room6/theme", headers=_auth(tok))
    assert r.status_code == 200
    r = client.get("/api/rooms/theme-room6/theme", headers=_auth(tok))
    assert r.get_json()["is_custom"] is False


def test_reset_without_theme(client):
    tok = _reg(client, "theme_g")
    r = client.delete("/api/rooms/theme-empty/theme", headers=_auth(tok))
    assert r.status_code == 404
