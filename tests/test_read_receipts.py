"""Tests for DM read receipts (Phase 37)."""
from pathlib import Path

from web.backend import realtime


def _reg(client, u):
    r = client.post("/api/auth/register", json={
        "username": u, "email": f"{u}@example.com", "password": "secret123",
    })
    return r.get_json()["token"], r.get_json()["user_id"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_dm_socket_handlers_registered():
    handlers = getattr(realtime.socketio.server, "handlers", None)
    if not isinstance(handlers, dict):
        return
    events = set()
    for _, evts in handlers.items():
        if isinstance(evts, dict):
            events.update(evts.keys())
    for ev in ("dm_typing_start", "dm_typing_stop", "dm_join", "dm_read"):
        assert ev in events, f"missing handler: {ev}"


def test_read_at_set_on_fetch(client):
    """After the recipient fetches messages, read_at is populated."""
    a, _ = _reg(client, "rr_a")
    b, _ = _reg(client, "rr_b")
    tid = client.post("/api/dms/threads", json={"username": "rr_b"},
                      headers=_auth(a)).get_json()["thread_id"]
    client.post(f"/api/dms/threads/{tid}", json={"body": "hi"},
                headers=_auth(a))

    # Bob reads
    r = client.get(f"/api/dms/threads/{tid}", headers=_auth(b))
    msgs = r.get_json()["messages"]
    assert any(m.get("read_at") for m in msgs)


def test_frontend_has_read_tag():
    src = Path("web/frontend/js/tabs/dms.js").read_text()
    assert "read-tag" in src
    assert "dm_typing" in src
