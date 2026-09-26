"""Tests for custom emoji packs (Phase 61)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_emoji_requires_auth(client):
    assert client.get("/api/emoji_packs").status_code == 401


def test_create_pack(client):
    tok = _reg(client, "em_a")
    r = client.post("/api/emoji_packs", json={"name": "Party"}, headers=_auth(tok))
    assert r.status_code == 201
    assert r.get_json()["name"] == "Party"


def test_add_and_list_items(client):
    tok = _reg(client, "em_b")
    pack_id = client.post("/api/emoji_packs", json={"name": "Faces"},
                          headers=_auth(tok)).get_json()["id"]

    r = client.post(f"/api/emoji_packs/{pack_id}/items",
                    json={"name": "smile", "emoji": "😀"}, headers=_auth(tok))
    assert r.status_code == 201

    r = client.get(f"/api/emoji_packs/{pack_id}", headers=_auth(tok))
    items = r.get_json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "smile"


def test_invalid_item_name(client):
    tok = _reg(client, "em_c")
    pack_id = client.post("/api/emoji_packs", json={"name": "X"},
                          headers=_auth(tok)).get_json()["id"]
    r = client.post(f"/api/emoji_packs/{pack_id}/items",
                    json={"name": "BAD NAME!", "emoji": "😀"}, headers=_auth(tok))
    assert r.status_code == 400


def test_item_requires_emoji_or_url(client):
    tok = _reg(client, "em_d")
    pack_id = client.post("/api/emoji_packs", json={"name": "X"},
                          headers=_auth(tok)).get_json()["id"]
    r = client.post(f"/api/emoji_packs/{pack_id}/items",
                    json={"name": "empty"}, headers=_auth(tok))
    assert r.status_code == 400


def test_cannot_add_to_others_pack(client):
    tok_a = _reg(client, "em_a1")
    tok_b = _reg(client, "em_b1")
    pack_id = client.post("/api/emoji_packs", json={"name": "Mine"},
                          headers=_auth(tok_a)).get_json()["id"]
    r = client.post(f"/api/emoji_packs/{pack_id}/items",
                    json={"name": "evil", "emoji": "😈"}, headers=_auth(tok_b))
    assert r.status_code == 403


def test_public_pack_visible_to_all(client):
    tok_a = _reg(client, "em_a2")
    tok_b = _reg(client, "em_b2")
    client.post("/api/emoji_packs",
                json={"name": "Public", "is_public": True}, headers=_auth(tok_a))
    r = client.get("/api/emoji_packs", headers=_auth(tok_b))
    names = [p["name"] for p in r.get_json()["packs"]]
    assert "Public" in names
