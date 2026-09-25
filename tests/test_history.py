"""Tests for the calculation history blueprint."""


def _register_and_token(client, username="hist_user"):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_history_requires_auth(client):
    r = client.get("/api/history")
    assert r.status_code == 401


def test_save_and_list(client):
    token = _register_and_token(client)
    r = client.post("/api/history", json={
        "expression": "5 + 3", "result": "8", "operation": "add",
    }, headers=_auth(token))
    assert r.status_code == 201

    r = client.get("/api/history", headers=_auth(token))
    assert r.status_code == 200
    items = r.get_json()
    assert len(items) == 1
    assert items[0]["expression"] == "5 + 3"
    assert items[0]["result"] == "8"


def test_save_missing_fields(client):
    token = _register_and_token(client, "hist_user2")
    r = client.post("/api/history", json={"expression": "5 + 3"}, headers=_auth(token))
    assert r.status_code == 400


def test_users_isolated(client):
    t1 = _register_and_token(client, "alice_x")
    t2 = _register_and_token(client, "bob_x")
    client.post("/api/history", json={"expression": "1+1", "result": "2"},
                headers=_auth(t1))
    r = client.get("/api/history", headers=_auth(t2))
    assert r.get_json() == []


def test_delete_entry(client):
    token = _register_and_token(client, "del_user")
    saved = client.post("/api/history", json={"expression": "1+1", "result": "2"},
                        headers=_auth(token)).get_json()
    r = client.delete(f"/api/history/{saved['id']}", headers=_auth(token))
    assert r.status_code == 200
    r2 = client.get("/api/history", headers=_auth(token))
    assert r2.get_json() == []


def test_clear_all(client):
    token = _register_and_token(client, "clear_user")
    for i in range(3):
        client.post("/api/history", json={"expression": f"{i}+1", "result": str(i+1)},
                    headers=_auth(token))
    r = client.delete("/api/history", headers=_auth(token))
    assert r.get_json()["deleted_count"] == 3
    r2 = client.get("/api/history", headers=_auth(token))
    assert r2.get_json() == []
