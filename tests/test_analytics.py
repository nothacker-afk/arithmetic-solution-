"""Tests for admin analytics (Phase 60)."""


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"], r.get_json()["user_id"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_analytics_requires_admin(client):
    """Second user is not admin (admin = user id 1)."""
    _reg(client, "an_admin")
    tok2, _ = _reg(client, "an_regular")
    r = client.get("/api/admin/analytics", headers=_auth(tok2))
    assert r.status_code == 403


def test_analytics_overview(client):
    tok, _ = _reg(client, "an_admin2")
    r = client.get("/api/admin/analytics?days=7", headers=_auth(tok))
    assert r.status_code == 200
    data = r.get_json()
    assert data["days"] == 7
    assert "totals" in data
    assert "series" in data
    # series should have exactly 7 points per category
    for name, pts in data["series"].items():
        assert len(pts) == 7, f"{name} series should have 7 points"


def test_analytics_top_users(client):
    tok, _ = _reg(client, "an_admin3")
    # Create a message so top_users is non-empty
    client.post("/api/chat/analytics-room",
                json={"username": "an_admin3", "body": "hi"})
    r = client.get("/api/admin/analytics/users?days=7", headers=_auth(tok))
    assert r.status_code == 200
    assert "top_users" in r.get_json()


def test_analytics_top_rooms(client):
    tok, _ = _reg(client, "an_admin4")
    client.post("/api/chat/analytics-room2",
                json={"username": "an_admin4", "body": "hi"})
    r = client.get("/api/admin/analytics/rooms?limit=5", headers=_auth(tok))
    assert r.status_code == 200
    assert "top_rooms" in r.get_json()
