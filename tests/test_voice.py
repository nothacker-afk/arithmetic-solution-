"""Tests for voice messages (Phase 31)."""
import base64


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def test_upload_requires_auth(client):
    r = client.post("/api/voice", json={"ciphertext_b64": "x"})
    assert r.status_code == 401


def test_upload_and_download(client):
    tok = _reg(client, "voice_user1")
    payload = b"\x00\x01fake-audio-bytes"
    b64 = base64.b64encode(payload).decode()
    r = client.post("/api/voice", json={
        "ciphertext_b64": b64, "duration_ms": 1234, "mime": "audio/webm",
    }, headers=_auth(tok))
    assert r.status_code == 201
    clip_id = r.get_json()["id"]
    assert r.get_json()["duration_ms"] == 1234

    r = client.get(f"/api/voice/{clip_id}")
    assert r.status_code == 200
    assert r.data == payload


def test_upload_missing_payload(client):
    tok = _reg(client, "voice_user2")
    r = client.post("/api/voice", json={}, headers=_auth(tok))
    assert r.status_code == 400


def test_upload_invalid_base64(client):
    tok = _reg(client, "voice_user3")
    r = client.post("/api/voice", json={"ciphertext_b64": "!!!"},
                    headers=_auth(tok))
    assert r.status_code == 400


def test_invalid_clip_id(client):
    assert client.get("/api/voice/not-hex").status_code == 400


def test_missing_clip(client):
    assert client.get("/api/voice/" + "a" * 32).status_code == 404


def test_list_my_clips(client):
    tok = _reg(client, "voice_user4")
    for _ in range(2):
        client.post("/api/voice", json={
            "ciphertext_b64": base64.b64encode(b"x").decode(),
        }, headers=_auth(tok))
    r = client.get("/api/voice", headers=_auth(tok))
    assert r.status_code == 200
    assert len(r.get_json()["clips"]) == 2


def test_delete_only_uploader(client):
    t1 = _reg(client, "voice_a")
    t2 = _reg(client, "voice_b")
    clip = client.post("/api/voice", json={
        "ciphertext_b64": base64.b64encode(b"y").decode(),
    }, headers=_auth(t1)).get_json()["id"]

    r = client.delete(f"/api/voice/{clip}", headers=_auth(t2))
    assert r.status_code == 403

    r = client.delete(f"/api/voice/{clip}", headers=_auth(t1))
    assert r.status_code == 200


def test_chat_message_with_voice_attachment(client):
    tok = _reg(client, "voice_chat1")
    clip = client.post("/api/voice", json={
        "ciphertext_b64": base64.b64encode(b"z").decode(),
        "duration_ms": 500,
    }, headers=_auth(tok)).get_json()["id"]

    r = client.post("/api/chat/voice-room", json={
        "username": "voice_chat1", "body": "", "encrypted": True,
        "kind": "voice", "attachment_id": clip,
    })
    assert r.status_code == 201
    assert r.get_json()["kind"] == "voice"
    assert r.get_json()["attachment_id"] == clip
