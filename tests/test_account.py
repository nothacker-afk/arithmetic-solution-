"""Tests for account data ownership (Phase 17)."""
import base64
import io
import json
import zipfile

import pytest


def _register(client, username):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secret123",
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"], r.get_json()["user_id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------
# Data summary
# ---------------------------------------------------------------------
def test_summary_requires_auth(client):
    assert client.get("/api/account/data-summary").status_code == 401


def test_summary_shape(client):
    tok, uid = _register(client, "summary_user")
    r = client.get("/api/account/data-summary", headers=_auth(tok))
    assert r.status_code == 200
    data = r.get_json()
    assert data["user"]["id"] == uid
    assert "calculations" in data
    assert "rooms_joined" in data
    assert "retention_policy" in data
    assert isinstance(data["retention_policy"], dict)


# ---------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------
def test_export_requires_auth(client):
    assert client.get("/api/account/export").status_code == 401


def test_export_json(client):
    tok, uid = _register(client, "export_user")
    # create some data
    client.post("/api/history", json={"expression": "1+1", "result": "2"},
                headers=_auth(tok))
    client.post("/api/rooms/exp-room/claim", json={}, headers=_auth(tok))

    r = client.get("/api/account/export?format=json", headers=_auth(tok))
    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    data = json.loads(r.data)
    assert data["user"]["id"] == uid
    assert len(data["calculations"]) == 1
    assert any(r["name"] == "exp-room" for r in data["rooms"])


def test_export_zip(client):
    tok, uid = _register(client, "zip_user")
    r = client.get("/api/account/export?format=zip", headers=_auth(tok))
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("application/zip")

    with zipfile.ZipFile(io.BytesIO(r.data)) as zf:
        names = zf.namelist()
        assert "account.json" in names
        assert "README.txt" in names
        content = json.loads(zf.read("account.json"))
        assert content["user"]["id"] == uid


def test_export_bad_format(client):
    tok, _ = _register(client, "badfmt_user")
    r = client.get("/api/account/export?format=xml", headers=_auth(tok))
    assert r.status_code == 400


# ---------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------
def test_delete_requires_confirmation(client):
    tok, _ = _register(client, "del_user1")
    r = client.delete("/api/account", json={"password": "secret123"},
                      headers=_auth(tok))
    assert r.status_code == 400


def test_delete_wrong_password(client):
    tok, _ = _register(client, "del_user2")
    r = client.delete("/api/account",
                      json={"password": "wrongpass", "confirm": "DELETE"},
                      headers=_auth(tok))
    assert r.status_code == 401


def test_delete_full_flow(client):
    tok, uid = _register(client, "del_user3")

    # create data
    client.post("/api/history", json={"expression": "1+1", "result": "2"},
                headers=_auth(tok))
    client.post("/api/rooms/del-room/claim", json={}, headers=_auth(tok))
    client.post("/api/chat/del-room",
                json={"username": "del_user3", "body": "hi"})

    r = client.delete("/api/account",
                      json={"password": "secret123", "confirm": "DELETE"},
                      headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["deleted"] is True

    # Verify user is gone
    r = client.get("/api/auth/me", headers=_auth(tok))
    assert r.status_code == 401  # token references a deleted user

    # Verify data cascade
    tok2, _ = _register(client, "del_checker")
    assert tok2  # admin by chance
    r = client.get("/api/admin/users", headers=_auth(tok2))
    if r.status_code == 200:
        usernames = [u["username"] for u in r.get_json()["users"]]
        assert "del_user3" not in usernames


def test_delete_transfers_owned_room(client):
    """When owner deletes account, room goes to oldest other member."""
    owner_tok, _ = _register(client, "room_owner")
    member_tok, _ = _register(client, "room_member")

    # owner claims a room
    client.post("/api/rooms/transfer-room/claim", json={}, headers=_auth(owner_tok))

    # generate an invite and have member join
    inv = client.post("/api/rooms/transfer-room/invites", json={},
                      headers=_auth(owner_tok)).get_json()
    client.post("/api/rooms/transfer-room/join",
                json={"invite": inv["token"]}, headers=_auth(member_tok))

    # owner deletes account
    r = client.delete("/api/account",
                      json={"password": "secret123", "confirm": "DELETE"},
                      headers=_auth(owner_tok))
    assert r.status_code == 200

    # Room should still exist, now owned by member
    info = client.get("/api/rooms/transfer-room").get_json()
    assert info["registered"] is True
    assert info["member_count"] == 1

    members = client.get("/api/rooms/transfer-room/members",
                         headers=_auth(member_tok)).get_json()["members"]
    assert members[0]["username"] == "room_member"
    assert members[0]["role"] == "owner"


def test_delete_deletes_empty_owned_room(client):
    """Owner of an empty room → room gets deleted."""
    tok, _ = _register(client, "solo_owner")
    client.post("/api/rooms/solo-room/claim", json={}, headers=_auth(tok))

    client.delete("/api/account",
                  json={"password": "secret123", "confirm": "DELETE"},
                  headers=_auth(tok))

    info = client.get("/api/rooms/solo-room").get_json()
    assert info["registered"] is False


# ---------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------
def test_backups_empty(client):
    tok, _ = _register(client, "backup_user1")
    r = client.get("/api/account/backups", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["backups"] == []


def test_create_backup(client):
    tok, uid = _register(client, "backup_user2")
    payload = b"this is a fake encrypted backup"
    b64 = base64.b64encode(payload).decode()

    r = client.post("/api/account/backups",
                    json={"label": "test backup", "ciphertext_b64": b64},
                    headers=_auth(tok))
    assert r.status_code == 201
    data = r.get_json()
    assert data["size_bytes"] == len(payload)
    assert data["label"] == "test backup"

    # List should show it
    r = client.get("/api/account/backups", headers=_auth(tok))
    assert len(r.get_json()["backups"]) == 1


def test_create_backup_invalid_base64(client):
    tok, _ = _register(client, "backup_user3")
    r = client.post("/api/account/backups",
                    json={"ciphertext_b64": "!!!not-base64!!!"},
                    headers=_auth(tok))
    assert r.status_code == 400


def test_download_backup(client):
    tok, _ = _register(client, "backup_user4")
    payload = b"some bytes here"
    b64 = base64.b64encode(payload).decode()
    backup_id = client.post("/api/account/backups",
                            json={"ciphertext_b64": b64},
                            headers=_auth(tok)).get_json()["id"]

    r = client.get(f"/api/account/backups/{backup_id}", headers=_auth(tok))
    assert r.status_code == 200
    assert r.data == payload


def test_download_backup_wrong_user(client):
    tok1, _ = _register(client, "backup_owner")
    tok2, _ = _register(client, "backup_other")

    payload = b"secret"
    b64 = base64.b64encode(payload).decode()
    backup_id = client.post("/api/account/backups",
                            json={"ciphertext_b64": b64},
                            headers=_auth(tok1)).get_json()["id"]

    r = client.get(f"/api/account/backups/{backup_id}", headers=_auth(tok2))
    assert r.status_code == 404


def test_delete_backup(client):
    tok, _ = _register(client, "backup_user5")
    payload = b"x"
    b64 = base64.b64encode(payload).decode()
    backup_id = client.post("/api/account/backups",
                            json={"ciphertext_b64": b64},
                            headers=_auth(tok)).get_json()["id"]

    r = client.delete(f"/api/account/backups/{backup_id}", headers=_auth(tok))
    assert r.status_code == 200

    r = client.get(f"/api/account/backups/{backup_id}", headers=_auth(tok))
    assert r.status_code == 404


def test_invalid_backup_id(client):
    tok, _ = _register(client, "backup_user6")
    r = client.get("/api/account/backups/not-hex", headers=_auth(tok))
    assert r.status_code == 400
