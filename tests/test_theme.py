"""Tests for theme + language preferences (Phase 12)."""


def _register(client, username):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secret123",
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_get_prefs_requires_auth(client):
    assert client.get("/api/prefs").status_code == 401


def test_set_prefs_requires_auth(client):
    r = client.put("/api/prefs", json={"theme": "dark", "language": "fr"})
    assert r.status_code == 401


def test_defaults_when_unset(client):
    tok = _register(client, "pref_user1")
    r = client.get("/api/prefs", headers=_auth(tok))
    assert r.status_code == 200
    body = r.get_json()
    assert body["theme"] == "auto"
    assert body["language"] == "en"


def test_set_and_get_roundtrip(client):
    tok = _register(client, "pref_user2")
    r = client.put("/api/prefs",
                   json={"theme": "dark", "language": "fr"},
                   headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json() == {"theme": "dark", "language": "fr"}

    r = client.get("/api/prefs", headers=_auth(tok))
    assert r.get_json() == {"theme": "dark", "language": "fr"}


def test_invalid_theme(client):
    tok = _register(client, "pref_user3")
    r = client.put("/api/prefs",
                   json={"theme": "neon", "language": "en"},
                   headers=_auth(tok))
    assert r.status_code == 400


def test_invalid_language(client):
    tok = _register(client, "pref_user4")
    r = client.put("/api/prefs",
                   json={"theme": "dark", "language": "xx"},
                   headers=_auth(tok))
    assert r.status_code == 400


def test_update_overwrites(client):
    tok = _register(client, "pref_user5")
    for theme, lang in [("light", "en"), ("dark", "es"), ("auto", "sw")]:
        client.put("/api/prefs",
                   json={"theme": theme, "language": lang},
                   headers=_auth(tok))
    r = client.get("/api/prefs", headers=_auth(tok))
    assert r.get_json() == {"theme": "auto", "language": "sw"}


def test_users_isolated(client):
    t1 = _register(client, "pref_alice")
    t2 = _register(client, "pref_bob")
    client.put("/api/prefs",
               json={"theme": "dark", "language": "fr"},
               headers=_auth(t1))
    assert client.get("/api/prefs", headers=_auth(t2)).get_json() == {
        "theme": "auto", "language": "en",
    }
