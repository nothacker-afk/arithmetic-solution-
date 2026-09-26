"""Tests for passkey endpoints (Phase 25).

Full WebAuthn flows require real browsers, so these tests focus on
endpoint availability, error paths, and graceful degradation.
"""
import pytest


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _register(client, username):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secret123",
    })
    return r.get_json()["token"]


def test_availability_endpoint(client):
    r = client.get("/api/passkeys/available")
    assert r.status_code == 200
    body = r.get_json()
    assert "available" in body
    assert "rp_id" in body


def test_register_requires_auth(client):
    r = client.post("/api/passkeys/register/begin", json={})
    assert r.status_code == 401


def test_login_begin_requires_username(client):
    r = client.post("/api/passkeys/login/begin", json={})
    assert r.status_code == 400


def test_login_begin_unknown_user(client):
    r = client.post("/api/passkeys/login/begin", json={"username": "nonexistent"})
    assert r.status_code == 404


def test_list_passkeys_requires_auth(client):
    r = client.get("/api/passkeys")
    assert r.status_code == 401


def test_list_passkeys_empty(client):
    tok = _register(client, "pk_user1")
    r = client.get("/api/passkeys", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["passkeys"] == []


def test_register_begin_reports_missing_sdk(client):
    """If `webauthn` is not installed, register/begin returns 503."""
    tok = _register(client, "pk_user2")
    r = client.post("/api/passkeys/register/begin", json={}, headers=_auth(tok))
    # 200 if webauthn installed; 503 if not — never 500
    assert r.status_code in (200, 503)


def test_delete_nonexistent_passkey(client):
    tok = _register(client, "pk_user3")
    r = client.delete("/api/passkeys/does-not-exist", headers=_auth(tok))
    assert r.status_code == 404


def test_login_finish_unknown_challenge(client):
    tok = _register(client, "pk_user4")
    r = client.post("/api/passkeys/login/finish",
                    json={"username": "pk_user4", "credential": {}})
    # Either 400 (missing challenge) or 503 (sdk missing)
    assert r.status_code in (400, 401, 503)
