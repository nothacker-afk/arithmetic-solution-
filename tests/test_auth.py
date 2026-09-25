"""Tests for the JWT auth blueprint."""


def test_register_success(client):
    r = client.post("/api/auth/register", json={
        "username": "alice", "email": "alice@example.com", "password": "secret123",
    })
    assert r.status_code == 201
    data = r.get_json()
    assert "token" in data
    assert data["username"] == "alice"


def test_register_missing_fields(client):
    r = client.post("/api/auth/register", json={"username": "bob"})
    assert r.status_code == 400


def test_register_short_password(client):
    r = client.post("/api/auth/register", json={
        "username": "bob", "email": "bob@example.com", "password": "short",
    })
    assert r.status_code == 400


def test_register_duplicate(client):
    payload = {"username": "carl", "email": "carl@example.com", "password": "secret123"}
    r1 = client.post("/api/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/auth/register", json=payload)
    assert r2.status_code == 409


def test_login_success(client):
    client.post("/api/auth/register", json={
        "username": "dave", "email": "dave@example.com", "password": "secret123",
    })
    r = client.post("/api/auth/login", json={"username": "dave", "password": "secret123"})
    assert r.status_code == 200
    assert "token" in r.get_json()


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={
        "username": "eve", "email": "eve@example.com", "password": "secret123",
    })
    r = client.post("/api/auth/login", json={"username": "eve", "password": "wrongpass"})
    assert r.status_code == 401


def test_me_requires_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_with_token(client):
    reg = client.post("/api/auth/register", json={
        "username": "fred", "email": "fred@example.com", "password": "secret123",
    })
    token = reg.get_json()["token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.get_json()["username"] == "fred"


def test_me_invalid_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
