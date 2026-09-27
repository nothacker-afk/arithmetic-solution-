"""Tests for multi-device sync (Phase 67)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_register_device(client):
    tok = _reg(client, "sync_a")
    r = client.post("/api/sync/devices/register",
                    json={"device_id": "device-abc12345", "label": "Pixel"},
                    headers=_auth(tok))
    assert r.status_code == 201
    assert r.get_json()["device_id"] == "device-abc12345"


def test_register_invalid_device_id(client):
    tok = _reg(client, "sync_b")
    r = client.post("/api/sync/devices/register",
                    json={"device_id": "x"}, headers=_auth(tok))
    assert r.status_code == 400


def test_list_devices(client):
    tok = _reg(client, "sync_c")
    for did in ("device-aaaa1111", "device-bbbb2222"):
        client.post("/api/sync/devices/register",
                    json={"device_id": did}, headers=_auth(tok))
    r = client.get("/api/sync/devices", headers=_auth(tok))
    assert len(r.get_json()["devices"]) == 2


def test_remove_device(client):
    tok = _reg(client, "sync_d")
    client.post("/api/sync/devices/register",
                json={"device_id": "device-xxxx9999"}, headers=_auth(tok))
    r = client.delete("/api/sync/devices/device-xxxx9999", headers=_auth(tok))
    assert r.status_code == 200
    assert client.get("/api/sync/devices", headers=_auth(tok)).get_json()["devices"] == []


def test_set_read_state(client):
    tok = _reg(client, "sync_e")
    client.post("/api/sync/devices/register",
                json={"device_id": "device-read1111"}, headers=_auth(tok))
    r = client.post("/api/sync/read-state", json={
        "device_id": "device-read1111",
        "room_id": "sync-room",
        "last_read_message_id": 5,
    }, headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["last_read_message_id"] == 5


def test_read_state_no_regression(client):
    tok = _reg(client, "sync_f")
    client.post("/api/sync/read-state", json={
        "device_id": "device-regr1111", "room_id": "r", "last_read_message_id": 10,
    }, headers=_auth(tok))
    r = client.post("/api/sync/read-state", json={
        "device_id": "device-regr1111", "room_id": "r", "last_read_message_id": 3,
    }, headers=_auth(tok))
    assert r.get_json().get("no_change") is True


def test_aggregate_across_devices(client):
    tok = _reg(client, "sync_g")
    for did, mid in (("device-agg11111", 5), ("device-agg22222", 8)):
        client.post("/api/sync/devices/register", json={"device_id": did}, headers=_auth(tok))
        client.post("/api/sync/read-state", json={
            "device_id": did, "room_id": "agg-room", "last_read_message_id": mid,
        }, headers=_auth(tok))

    r = client.get("/api/sync/aggregate?room_id=agg-room", headers=_auth(tok))
    assert r.status_code == 200
    data = r.get_json()
    assert data["max_read"] == 8
    assert data["min_read"] == 5
    assert data["device_count"] == 2
