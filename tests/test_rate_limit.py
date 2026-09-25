"""Tests for the in-memory rate limiter."""
import pytest
from web.backend.rate_limit import rate_limit, reset


@pytest.fixture(autouse=True)
def _clear():
    reset()
    yield
    reset()


@pytest.fixture
def limited_client():
    """Flask client with a strict rate-limited test route."""
    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route("/limited")
    @rate_limit(max_calls=3, window_seconds=60)
    def limited():
        return jsonify({"ok": True})

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_allows_under_limit(limited_client):
    for _ in range(3):
        r = limited_client.get("/limited")
        assert r.status_code == 200


def test_blocks_over_limit(limited_client):
    for _ in range(3):
        limited_client.get("/limited")
    r = limited_client.get("/limited")
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_reset_clears_state(limited_client):
    for _ in range(3):
        limited_client.get("/limited")
    reset()
    r = limited_client.get("/limited")
    assert r.status_code == 200
