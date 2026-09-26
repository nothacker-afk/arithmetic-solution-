"""Tests for bot API (Phase 43)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _bot_auth(t):
    return {"Authorization": f"Bot {t}"}


def test_create_bot_requires_room_owner(client):
    a = _reg(client, "bot_owner")
    b = _reg(client, "bot_other")
    client.post("/api/rooms/bot-room/claim", json={}, headers=_auth(a))

    r = client.post("/api/bots", json={"room_id": "bot-room", "name": "helper"},
                    headers=_auth(b))
    assert r.status_code == 403


def test_create_bot_success(client):
    a = _reg(client, "bot_owner2")
    client.post("/api/rooms/bot-room2/claim", json={}, headers=_auth(a))

    r = client.post("/api/bots", json={"room_id": "bot-room2", "name": "helper"},
                    headers=_auth(a))
    assert r.status_code == 201
    data = r.get_json()
    assert data["id"]
    assert data["token"]
    assert "help" in data["commands"]


def test_bot_can_post(client):
    a = _reg(client, "bot_owner3")
    client.post("/api/rooms/bot-room3/claim", json={}, headers=_auth(a))
    bot = client.post("/api/bots", json={"room_id": "bot-room3", "name": "testbot"},
                      headers=_auth(a)).get_json()

    r = client.post(f"/api/bots/{bot['id']}/messages",
                    json={"body": "!echo hello"},
                    headers=_bot_auth(bot["token"]))
    assert r.status_code == 201
    assert "hello" in r.get_json()["body"]
    assert r.get_json()["username"] == "testbot"


def test_bot_help_command(client):
    a = _reg(client, "bot_owner4")
    client.post("/api/rooms/bot-room4/claim", json={}, headers=_auth(a))
    bot = client.post("/api/bots", json={"room_id": "bot-room4", "name": "helpbot"},
                      headers=_auth(a)).get_json()

    r = client.post(f"/api/bots/{bot['id']}/messages",
                    json={"body": "!help"}, headers=_bot_auth(bot["token"]))
    assert r.status_code == 201
    assert "Commands:" in r.get_json()["body"]


def test_bot_roll_command(client):
    a = _reg(client, "bot_owner5")
    client.post("/api/rooms/bot-room5/claim", json={}, headers=_auth(a))
    bot = client.post("/api/bots", json={"room_id": "bot-room5", "name": "roller"},
                      headers=_auth(a)).get_json()

    r = client.post(f"/api/bots/{bot['id']}/messages",
                    json={"body": "!roll 100"}, headers=_bot_auth(bot["token"]))
    assert r.status_code == 201
    assert "🎲" in r.get_json()["body"]


def test_bot_invalid_token(client):
    r = client.post("/api/bots/fakeid/messages",
                    json={"body": "test"},
                    headers=_bot_auth("invalid-token-here"))
    assert r.status_code == 401


def test_bot_without_token(client):
    r = client.post("/api/bots/fakeid/messages", json={"body": "test"})
    assert r.status_code == 401


def test_bot_me(client):
    a = _reg(client, "bot_owner6")
    client.post("/api/rooms/bot-room6/claim", json={}, headers=_auth(a))
    bot = client.post("/api/bots", json={"room_id": "bot-room6", "name": "whoami"},
                      headers=_auth(a)).get_json()

    r = client.get("/api/bots/me", headers=_bot_auth(bot["token"]))
    assert r.status_code == 200
    assert r.get_json()["name"] == "whoami"
    assert r.get_json()["room_id"] == "bot-room6"


def test_delete_bot(client):
    a = _reg(client, "bot_owner7")
    client.post("/api/rooms/bot-room7/claim", json={}, headers=_auth(a))
    bot = client.post("/api/bots", json={"room_id": "bot-room7", "name": "bye"},
                      headers=_auth(a)).get_json()

    r = client.delete(f"/api/bots/{bot['id']}", headers=_auth(a))
    assert r.status_code == 200
    r = client.get("/api/bots", headers=_auth(a))
    assert all(b["id"] != bot["id"] for b in r.get_json()["bots"])
