"""Tests for room templates (Phase 59)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_list_templates(client):
    r = client.get("/api/room_templates")
    assert r.status_code == 200
    ids = [t["id"] for t in r.get_json()["templates"]]
    assert "blank" in ids
    assert "project" in ids
    assert "study" in ids


def test_get_template_detail(client):
    r = client.get("/api/room_templates/project")
    assert r.status_code == 200
    data = r.get_json()
    assert data["name"] == "Project"
    assert len(data["wiki"]) >= 1


def test_get_unknown_template(client):
    r = client.get("/api/room_templates/nope")
    assert r.status_code == 404


def test_apply_template(client):
    tok = _reg(client, "tpl_a")
    r = client.post("/api/rooms/tpl-room/apply_template",
                    json={"template_id": "project"}, headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["wiki_pages_created"] >= 1

    # Verify pages exist
    r = client.get("/api/rooms/tpl-room/wiki", headers=_auth(tok))
    titles = [p["title"] for p in r.get_json()["pages"]]
    assert "Project Brief" in titles


def test_applied_template(client):
    tok = _reg(client, "tpl_b")
    client.post("/api/rooms/tpl-room2/apply_template",
                json={"template_id": "community"}, headers=_auth(tok))
    r = client.get("/api/rooms/tpl-room2/applied_template", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["template_id"] == "community"


def test_apply_requires_owner(client):
    a = _reg(client, "tpl_owner")
    b = _reg(client, "tpl_other")
    client.post("/api/rooms/tpl-room3/claim", json={}, headers=_auth(a))
    r = client.post("/api/rooms/tpl-room3/apply_template",
                    json={"template_id": "project"}, headers=_auth(b))
    assert r.status_code == 403


def test_apply_unknown_template(client):
    tok = _reg(client, "tpl_c")
    r = client.post("/api/rooms/tpl-room4/apply_template",
                    json={"template_id": "nope"}, headers=_auth(tok))
    assert r.status_code == 404
