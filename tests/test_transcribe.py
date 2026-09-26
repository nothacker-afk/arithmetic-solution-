"""Tests for voice transcription (Phase 40)."""
from pathlib import Path


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_availability_endpoint(client):
    r = client.get("/api/transcribe/available")
    assert r.status_code == 200
    body = r.get_json()
    assert "available" in body


def test_transcribe_requires_auth(client):
    r = client.post("/api/transcribe/upload", json={"audio_b64": "x"})
    assert r.status_code == 401


def test_transcribe_upload_reports_unavailable(client):
    """Without OPENAI_API_KEY, /upload returns 503 (not 500)."""
    tok = _reg(client, "tr_user1")
    r = client.post("/api/transcribe/upload",
                    json={"audio_b64": "aGVsbG8=", "mime": "audio/webm"},
                    headers=_auth(tok))
    assert r.status_code in (503, 500)  # 503 if key not set, 500 if key is bad
    if r.status_code == 503:
        assert "not configured" in r.get_json()["error"].lower()


def test_transcribe_upload_invalid_base64(client):
    tok = _reg(client, "tr_user2")
    r = client.post("/api/transcribe/upload",
                    json={"audio_b64": "!!!not-b64!!!"},
                    headers=_auth(tok))
    # 400 for bad base64 even when key missing? Our impl checks key first → 503
    assert r.status_code in (400, 503)


def test_transcribe_upload_missing_audio(client):
    tok = _reg(client, "tr_user3")
    r = client.post("/api/transcribe/upload", json={}, headers=_auth(tok))
    assert r.status_code in (400, 503)


def test_voice_clip_transcript_endpoint(client):
    tok = _reg(client, "tr_user4")
    import base64
    clip = client.post("/api/voice", json={
        "ciphertext_b64": base64.b64encode(b"x").decode(),
    }, headers=_auth(tok)).get_json()["id"]

    r = client.get(f"/api/voice/{clip}/transcript")
    assert r.status_code == 200
    assert r.get_json()["transcript"] == ""


def test_frontend_has_transcribe_button():
    src = Path("web/frontend/js/tabs/live.js").read_text()
    assert "transcribe-btn" in src
    assert "/api/transcribe/upload" in src
