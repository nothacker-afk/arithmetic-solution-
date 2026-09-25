"""Tests for room management (Phase 11)."""
import pytest


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _register(client, username):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secret123",
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------
# Info / claim
# ---------------------------------------------------------------------
def test_unclaimed_room_is_open(client):
    r = client.get("/api/rooms/any-room")
    assert r.status_code == 200
    data = r.get_json()
    assert data["registered"] is False
    assert data["open"] is True


def test_claim_requires_auth(client):
    r = client.post("/api/rooms/my-room/claim", json={})
    assert r.status_code == 401


def test_claim_success(client):
    tok = _register(client, "owner1")
    r = client.post("/api/rooms/r1/claim", json={}, headers=_auth(tok))
    assert r.status_code == 201
    assert r.get_json()["owner_id"] > 0

    info = client.get("/api/rooms/r1").get_json()
    assert info["registered"] is True
    assert info["member_count"] == 1


def test_claim_with_password(client):
    tok = _register(client, "owner2")
    r = client.post("/api/rooms/r2/claim", json={"password": "topsecret"},
                    headers=_auth(tok))
    assert r.status_code == 201
    info = client.get("/api/rooms/r2").get_json()
    assert info["has_password"] is True


def test_claim_twice_conflicts(client):
    tok = _register(client, "owner3")
    client.post("/api/rooms/r3/claim", json={}, headers=_auth(tok))
    r = client.post("/api/rooms/r3/claim", json={}, headers=_auth(tok))
    assert r.status_code == 409


def test_claim_invalid_room_name(client):
    tok = _register(client, "owner4")
    r = client.post("/api/rooms/bad room/claim", json={}, headers=_auth(tok))
    assert r.status_code == 400


# ---------------------------------------------------------------------
# Invites
# ---------------------------------------------------------------------
def test_create_invite_requires_owner(client):
    owner = _register(client, "owner5")
    other = _register(client, "other5")
    client.post("/api/rooms/r5/claim", json={}, headers=_auth(owner))

    r = client.post("/api/rooms/r5/invites", json={}, headers=_auth(other))
    assert r.status_code == 403


def test_create_invite_success(client):
    tok = _register(client, "owner6")
    client.post("/api/rooms/r6/claim", json={}, headers=_auth(tok))
    r = client.post("/api/rooms/r6/invites",
                    json={"ttl_hours": 1}, headers=_auth(tok))
    assert r.status_code == 201
    data = r.get_json()
    assert "token" in data
    assert data["ttl_hours"] == 1
    assert "url" in data


def test_invite_ttl_validation(client):
    tok = _register(client, "owner7")
    client.post("/api/rooms/r7/claim", json={}, headers=_auth(tok))
    r = client.post("/api/rooms/r7/invites",
                    json={"ttl_hours": 10000}, headers=_auth(tok))
    assert r.status_code == 400


def test_invite_missing_room(client):
    tok = _register(client, "owner8")
    r = client.post("/api/rooms/nope/invites", json={}, headers=_auth(tok))
    assert r.status_code == 404


# ---------------------------------------------------------------------
# Join
# ---------------------------------------------------------------------
def test_join_with_invite(client):
    owner = _register(client, "owner9")
    guest = _register(client, "guest9")
    client.post("/api/rooms/r9/claim", json={}, headers=_auth(owner))
    inv = client.post("/api/rooms/r9/invites",
                      json={"ttl_hours": 1}, headers=_auth(owner)).get_json()

    r = client.post("/api/rooms/r9/join",
                    json={"invite": inv["token"]}, headers=_auth(guest))
    assert r.status_code == 200
    assert r.get_json()["joined"] is True


def test_join_with_invalid_invite(client):
    owner = _register(client, "owner10")
    guest = _register(client, "guest10")
    client.post("/api/rooms/r10/claim", json={}, headers=_auth(owner))

    r = client.post("/api/rooms/r10/join",
                    json={"invite": "bogus"}, headers=_auth(guest))
    assert r.status_code == 401


def test_join_with_password(client):
    owner = _register(client, "owner11")
    guest = _register(client, "guest11")
    client.post("/api/rooms/r11/claim",
                json={"password": "letmein"}, headers=_auth(owner))

    r = client.post("/api/rooms/r11/join",
                    json={"password": "letmein"}, headers=_auth(guest))
    assert r.status_code == 200


def test_join_with_wrong_password(client):
    owner = _register(client, "owner12")
    guest = _register(client, "guest12")
    client.post("/api/rooms/r12/claim",
                json={"password": "right"}, headers=_auth(owner))

    r = client.post("/api/rooms/r12/join",
                    json={"password": "wrong"}, headers=_auth(guest))
    assert r.status_code == 401


def test_join_private_without_credentials(client):
    owner = _register(client, "owner13")
    guest = _register(client, "guest13")
    client.post("/api/rooms/r13/claim", json={}, headers=_auth(owner))

    r = client.post("/api/rooms/r13/join", json={}, headers=_auth(guest))
    assert r.status_code == 401


def test_join_already_member(client):
    owner = _register(client, "owner14")
    client.post("/api/rooms/r14/claim", json={}, headers=_auth(owner))
    r = client.post("/api/rooms/r14/join", json={}, headers=_auth(owner))
    assert r.status_code == 200
    assert r.get_json().get("already_member") is True


# ---------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------
def test_list_members_requires_auth(client):
    r = client.get("/api/rooms/r/members")
    assert r.status_code == 401


def test_list_members_non_member_forbidden(client):
    owner = _register(client, "owner15")
    guest = _register(client, "guest15")
    client.post("/api/rooms/r15/claim", json={}, headers=_auth(owner))

    r = client.get("/api/rooms/r15/members", headers=_auth(guest))
    assert r.status_code == 403


def test_list_members_success(client):
    owner = _register(client, "owner16")
    guest = _register(client, "guest16")
    client.post("/api/rooms/r16/claim", json={}, headers=_auth(owner))
    inv = client.post("/api/rooms/r16/invites",
                      json={}, headers=_auth(owner)).get_json()
    client.post("/api/rooms/r16/join",
                json={"invite": inv["token"]}, headers=_auth(guest))

    r = client.get("/api/rooms/r16/members", headers=_auth(owner))
    assert r.status_code == 200
    members = r.get_json()["members"]
    usernames = sorted(m["username"] for m in members)
    assert usernames == ["guest16", "owner16"]


# ---------------------------------------------------------------------
# Kick
# ---------------------------------------------------------------------
def test_kick_requires_owner(client):
    owner = _register(client, "owner17")
    guest = _register(client, "guest17")
    client.post("/api/rooms/r17/claim", json={}, headers=_auth(owner))
    inv = client.post("/api/rooms/r17/invites",
                      json={}, headers=_auth(owner)).get_json()
    client.post("/api/rooms/r17/join",
                json={"invite": inv["token"]}, headers=_auth(guest))

    # guest tries to kick owner
    owner_id = client.get("/api/auth/me", headers=_auth(owner)).get_json()["id"]
    r = client.delete(f"/api/rooms/r17/members/{owner_id}", headers=_auth(guest))
    assert r.status_code == 403


def test_kick_success(client):
    owner = _register(client, "owner18")
    guest = _register(client, "guest18")
    client.post("/api/rooms/r18/claim", json={}, headers=_auth(owner))
    inv = client.post("/api/rooms/r18/invites",
                      json={}, headers=_auth(owner)).get_json()
    client.post("/api/rooms/r18/join",
                json={"invite": inv["token"]}, headers=_auth(guest))

    guest_id = client.get("/api/auth/me", headers=_auth(guest)).get_json()["id"]
    r = client.delete(f"/api/rooms/r18/members/{guest_id}", headers=_auth(owner))
    assert r.status_code == 200

    members = client.get("/api/rooms/r18/members", headers=_auth(owner)).get_json()["members"]
    assert all(m["username"] != "guest18" for m in members)


def test_kick_self_forbidden(client):
    owner = _register(client, "owner19")
    client.post("/api/rooms/r19/claim", json={}, headers=_auth(owner))
    owner_id = client.get("/api/auth/me", headers=_auth(owner)).get_json()["id"]

    r = client.delete(f"/api/rooms/r19/members/{owner_id}", headers=_auth(owner))
    assert r.status_code == 400


# ---------------------------------------------------------------------
# List my rooms
# ---------------------------------------------------------------------
def test_list_my_rooms(client):
    tok = _register(client, "owner20")
    for name in ("room-a", "room-b"):
        client.post(f"/api/rooms/{name}/claim", json={}, headers=_auth(tok))

    r = client.get("/api/rooms", headers=_auth(tok))
    assert r.status_code == 200
    names = [x["name"] for x in r.get_json()["rooms"]]
    assert "room-a" in names
    assert "room-b" in names


# ---------------------------------------------------------------------
# Delete room
# ---------------------------------------------------------------------
def test_delete_requires_owner(client):
    owner = _register(client, "owner21")
    guest = _register(client, "guest21")
    client.post("/api/rooms/r21/claim", json={}, headers=_auth(owner))

    r = client.delete("/api/rooms/r21", headers=_auth(guest))
    assert r.status_code == 403


def test_delete_success(client):
    tok = _register(client, "owner22")
    client.post("/api/rooms/r22/claim", json={}, headers=_auth(tok))
    r = client.delete("/api/rooms/r22", headers=_auth(tok))
    assert r.status_code == 200

    info = client.get("/api/rooms/r22").get_json()
    assert info["registered"] is False
