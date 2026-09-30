"""Tests for equation solver (Phase 89)."""
import pytest
from web.backend.calc_engine import solve_linear, CalcError


def test_basic():
    assert solve_linear("2x + 5 = 15", "x")["solution"] == 5.0


def test_both_sides():
    assert solve_linear("3x - 7 = 2x + 3", "x")["solution"] == 10.0


def test_negative():
    assert solve_linear("-4x = 8", "x")["solution"] == -2.0


def test_simple():
    assert solve_linear("x + 1 = 4", "x")["solution"] == 3.0


def test_fraction():
    assert solve_linear("x/2 + 3 = 7", "x")["solution"] == 8.0


def test_identity():
    r = solve_linear("2x = 2x", "x")
    assert r["solution"] is None
    assert "Infinite" in r["message"]


def test_contradiction():
    r = solve_linear("2x = 2x + 5", "x")
    assert r["solution"] is None
    assert "No solution" in r["message"]


def test_missing_equals():
    with pytest.raises(CalcError):
        solve_linear("2x + 5")


def test_non_linear_rejected():
    with pytest.raises(CalcError):
        solve_linear("x^2 = 4", "x")


def test_endpoint(client):
    tok = client.post("/api/auth/register", json={
        "username": "sv_a", "email": "sv@x.com", "password": "secret123",
    }).get_json()["token"]
    r = client.post("/api/calc/solve",
                    json={"equation": "2x + 5 = 15", "variable": "x"},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.get_json()["solution"] == 5.0


def test_endpoint_missing(client):
    tok = client.post("/api/auth/register", json={
        "username": "sv_b", "email": "svb@x.com", "password": "secret123",
    }).get_json()["token"]
    r = client.post("/api/calc/solve", json={},
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 400
