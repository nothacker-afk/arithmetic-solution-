"""Tests for full-text search (Phase 26)."""
import pytest
from web.backend import search as search_mod


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _register(client, username):
    r = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "secret123",
    })
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"]


def test_search_requires_auth(client):
    r = client.get("/api/search?q=test")
    assert r.status_code == 401


def test_search_empty_query(client):
    tok = _register(client, "search_user1")
    r = client.get("/api/search?q=", headers=_auth(tok))
    assert r.status_code == 200
    assert r.get_json()["count"] == 0


def test_search_query_too_long(client):
    tok = _register(client, "search_user2")
    r = client.get("/api/search?q=" + "x" * 500, headers=_auth(tok))
    assert r.status_code == 400


def test_search_calculations(client):
    tok = _register(client, "search_user3")
    client.post("/api/history", json={
        "expression": "42 * 7", "result": "294", "operation": "multiply",
    }, headers=_auth(tok))
    client.post("/api/history", json={
        "expression": "1 + 1", "result": "2", "operation": "add",
    }, headers=_auth(tok))

    r = client.get("/api/search?q=42", headers=_auth(tok))
    assert r.status_code == 200
    data = r.get_json()
    assert data["engine"] in ("fts5", "like")
    results = [x for x in data["results"] if x["kind"] == "calculation"]
    assert any("42" in x["expression"] for x in results)


def test_search_chat(client):
    tok = _register(client, "search_user4")
    client.post("/api/chat/search-room", json={
        "username": "search_user4", "body": "the quick brown fox",
    })

    r = client.get("/api/search?q=quick", headers=_auth(tok))
    results = [x for x in r.get_json()["results"] if x["kind"] == "chat"]
    assert len(results) >= 1
    assert "quick" in results[0]["body"]


def test_search_scope_calculations_only(client):
    tok = _register(client, "search_user5")
    client.post("/api/history", json={
        "expression": "unique_alpha_string", "result": "1",
    }, headers=_auth(tok))
    client.post("/api/chat/search-scope", json={
        "username": "search_user5", "body": "unique_alpha_string in chat",
    })

    r = client.get("/api/search?q=unique_alpha_string&scope=calculations",
                   headers=_auth(tok))
    kinds = {x["kind"] for x in r.get_json()["results"]}
    assert kinds == {"calculation"} or kinds == set()


def test_search_scope_chat_only(client):
    tok = _register(client, "search_user6")
    client.post("/api/history", json={
        "expression": "unique_beta_string", "result": "1",
    }, headers=_auth(tok))
    client.post("/api/chat/search-scope2", json={
        "username": "search_user6", "body": "unique_beta_string",
    })

    r = client.get("/api/search?q=unique_beta_string&scope=chat",
                   headers=_auth(tok))
    kinds = {x["kind"] for x in r.get_json()["results"]}
    assert "calculation" not in kinds


def test_search_isolated_per_user(client):
    """Calculations of another user must not appear."""
    tok1 = _register(client, "search_alice")
    tok2 = _register(client, "search_bob")
    client.post("/api/history", json={
        "expression": "alice_secret_42", "result": "1",
    }, headers=_auth(tok1))

    r = client.get("/api/search?q=alice_secret_42", headers=_auth(tok2))
    calcs = [x for x in r.get_json()["results"] if x["kind"] == "calculation"]
    assert calcs == []


def test_fts_available_callable():
    assert callable(search_mod.fts_available)
