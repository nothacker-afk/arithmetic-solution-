"""Tests for voice channels (Phase 53)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_list_channels_empty(client):
    tok = _reg(client, "vc_a")
    r = client.get("/api/rooms/vc-room/voice_channels", headers=_auth(tok))
    assert r.status_code == 200
    channels = {c["name"] for c in r.get_json()["channels"]}
    assert "main" in channels
    assert "afk" in channels


def test_join_leave(client):
    tok = _reg(client, "vc_b")
    r = client.post("/api/rooms/vc-room2/voice_channels/join",
                    json={"channel": "main"}, headers=_auth(tok))
    assert r.status_code == 201

    r = client.get("/api/rooms/vc-room2/voice_channels", headers=_auth(tok))
    main = [c for c in r.get_json()["channels"] if c["name"] == "main"][0]
    assert len(main["members"]) == 1

    r = client.post("/api/rooms/vc-room2/voice_channels/leave", json={},
                    headers=_auth(tok))
    assert r.status_code == 200


def test_mute(client):
    tok = _reg(client, "vc_c")
    client.post("/api/rooms/vc-room3/voice_channels/join",
                json={"channel": "main"}, headers=_auth(tok))
    r = client.post("/api/rooms/vc-room3/voice_channels/mute",
                    json={"muted": True}, headers=_auth(tok))
    assert r.get_json()["muted"] is True


def test_join_moves_between_channels(client):
    tok = _reg(client, "vc_d")
    client.post("/api/rooms/vc-room4/voice_channels/join",
                json={"channel": "main"}, headers=_auth(tok))
    client.post("/api/rooms/vc-room4/voice_channels/join",
                json={"channel": "afk"}, headers=_auth(tok))
    r = client.get("/api/rooms/vc-room4/voice_channels", headers=_auth(tok))
    channels = {c["name"]: c for c in r.get_json()["channels"]}
    assert len(channels["main"]["members"]) == 0
    assert len(channels["afk"]["members"]) == 1


def test_invalid_channel(client):
    tok = _reg(client, "vc_e")
    r = client.post("/api/rooms/vc-room5/voice_channels/join",
                    json={"channel": "bad channel!"}, headers=_auth(tok))
    assert r.status_code == 400
