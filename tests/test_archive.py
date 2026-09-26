"""Tests for room archive (Phase 66)."""
import io
import zipfile


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_archive_requires_owner(client):
    a = _reg(client, "arc_a")
    b = _reg(client, "arc_b")
    client.post("/api/rooms/arc-room/claim", json={}, headers=_auth(a))
    r = client.post("/api/rooms/arc-room/archive", headers=_auth(b))
    assert r.status_code == 403


def test_archive_creates_zip(client):
    a = _reg(client, "arc_c")
    client.post("/api/rooms/arc-room2/claim", json={}, headers=_auth(a))
    # Populate some content
    for i in range(3):
        client.post("/api/chat/arc-room2",
                    json={"username": "arc_c", "body": f"msg {i}"})
    client.post("/api/rooms/arc-room2/wiki",
                json={"title": "Notes", "body": "content"},
                headers=_auth(a))

    r = client.post("/api/rooms/arc-room2/archive", headers=_auth(a))
    assert r.status_code == 200
    assert "zip" in r.headers["Content-Type"]

    # Inspect ZIP
    with zipfile.ZipFile(io.BytesIO(r.data)) as zf:
        names = zf.namelist()
        assert "index.html" in names
        assert "messages.json" in names
        assert "wiki/notes.md" in names
        html = zf.read("index.html").decode()
        assert "arc-room2" in html
        assert "msg 0" in html


def test_list_archives(client):
    a = _reg(client, "arc_d")
    client.post("/api/rooms/arc-room3/claim", json={}, headers=_auth(a))
    client.post("/api/rooms/arc-room3/archive", headers=_auth(a))
    r = client.get("/api/rooms/arc-room3/archives", headers=_auth(a))
    assert r.status_code == 200
    assert len(r.get_json()["archives"]) == 1
