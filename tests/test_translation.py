"""Tests for message translation (Phase 83)."""
import os


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_availability_endpoint(client):
    r = client.get("/api/translate/available")
    assert r.status_code == 200
    body = r.get_json()
    assert "available" in body


def test_translate_text_requires_auth(client):
    r = client.post("/api/translate/text", json={"text": "hi", "target_lang": "fr"})
    assert r.status_code == 401


def test_translate_text_unconfigured(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    tok = _reg(client, "tr_a")
    r = client.post("/api/translate/text",
                    json={"text": "hello", "target_lang": "fr"},
                    headers=_auth(tok))
    assert r.status_code == 503


def test_translate_text_invalid_lang(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    tok = _reg(client, "tr_b")
    r = client.post("/api/translate/text",
                    json={"text": "hello", "target_lang": "!!!"},
                    headers=_auth(tok))
    assert r.status_code in (400, 503)


def test_translate_text_missing_fields(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    tok = _reg(client, "tr_c")
    r = client.post("/api/translate/text", json={}, headers=_auth(tok))
    assert r.status_code in (400, 503)


def test_get_cached_translation_none(client):
    tok = _reg(client, "tr_d")
    r = client.get("/api/translate/message?kind=chat&message_id=1&target_lang=fr",
                   headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json().get("cached") is False


def test_translate_message_invalid_kind(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    tok = _reg(client, "tr_e")
    r = client.post("/api/translate/message",
                    json={"kind": "wat", "message_id": 1, "target_lang": "fr", "text": "hi"},
                    headers=_auth(tok))
    assert r.status_code in (400, 503)
