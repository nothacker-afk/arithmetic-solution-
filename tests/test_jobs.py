"""Tests for retention jobs (Phase 24)."""
import os
from datetime import datetime, timedelta, timezone

import pytest

from web.backend import jobs


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, username):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secret123",
    })
    return r.get_json()["token"]


def test_retention_clears_expired_invites(client):
    """Expired invites should be purged on every run."""
    tok = _register(client, "ret_user")
    client.post("/api/rooms/ret-room/claim", json={}, headers=_auth(tok))
    inv = client.post("/api/rooms/ret-room/invites",
                      json={"ttl_hours": 1}, headers=_auth(tok)).get_json()

    # Manually backdate the invite to simulate expiry
    from web.backend.database import get_db
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with get_db() as conn:
        conn.execute("UPDATE room_invites SET expires_at = ? WHERE token = ?",
                     (past, inv["token"]))

    deleted = jobs.run_retention()
    assert deleted.get("room_invites", 0) >= 1


def test_retention_disabled_by_default(monkeypatch):
    """Jobs don't delete anything if TTLs are 0."""
    monkeypatch.delenv("RETENTION_CALC_DAYS", raising=False)
    monkeypatch.delenv("RETENTION_CHAT_DAYS", raising=False)
    monkeypatch.delenv("RETENTION_AUDIT_DAYS", raising=False)

    deleted = jobs.run_retention()
    # Only expired invites + old device tokens may be purged
    assert "calculations" not in deleted
    assert "chat_messages" not in deleted
    assert "audit_log" not in deleted


def test_retention_purges_old_calculations(client, monkeypatch):
    tok = _register(client, "ret_user2")
    client.post("/api/history", json={"expression": "1+1", "result": "2"},
                headers=_auth(tok))

    # Backdate the calculation
    from web.backend.database import get_db
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    with get_db() as conn:
        conn.execute("UPDATE calculations SET created_at = ?", (past,))

    monkeypatch.setenv("RETENTION_CALC_DAYS", "5")
    deleted = jobs.run_retention()
    assert deleted.get("calculations", 0) >= 1


def test_snapshot_shape():
    s = jobs.snapshot()
    assert "last_run" in s
    assert "ttls" in s
    assert "calculations_days" in s["ttls"]
    assert "enabled" in s


def test_admin_retention_endpoint(client):
    tok = _register(client, "ret_admin")
    r = client.get("/api/admin/retention", headers=_auth(tok))
    assert r.status_code == 200
    body = r.get_json()
    assert "ttls" in body
    assert "total_runs" in body


def test_admin_retention_run_endpoint(client):
    tok = _register(client, "ret_admin2")
    r = client.post("/api/admin/retention/run", headers=_auth(tok))
    assert r.status_code == 200
    assert "deleted" in r.get_json()
