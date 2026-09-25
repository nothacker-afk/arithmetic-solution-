"""Tests for the AI parsing engine."""
import pytest
from ai_engine.parser import parse_and_solve, ParseError


# -------------------------------------------------------------------------
# Rule-based parser tests
# -------------------------------------------------------------------------
def test_add_phrase():
    r = parse_and_solve("add 5 and 3")
    assert r["result"] == 8
    assert r["operation"] == "add"


def test_plus_symbol():
    r = parse_and_solve("5 + 3")
    assert r["result"] == 8


def test_subtract_from():
    r = parse_and_solve("subtract 3 from 10")
    assert r["result"] == 7


def test_multiply_phrase():
    r = parse_and_solve("multiply 4 by 7")
    assert r["result"] == 28


def test_divide_phrase():
    r = parse_and_solve("10 divided by 4")
    assert r["result"] == 2.5


def test_percent_of():
    r = parse_and_solve("what is 15% of 240")
    assert r["result"] == pytest.approx(36.0)
    assert r["operation"] == "percent_of"


def test_sqrt():
    r = parse_and_solve("square root of 81")
    assert r["result"] == 9.0


def test_factorial():
    r = parse_and_solve("factorial of 6")
    assert r["result"] == 720


def test_power():
    r = parse_and_solve("2 to the power of 10")
    assert r["result"] == 1024


def test_sin():
    r = parse_and_solve("sin of 0")
    assert r["result"] == pytest.approx(0.0)


def test_unparseable():
    with pytest.raises(ParseError):
        parse_and_solve("make me a sandwich")


def test_empty():
    with pytest.raises(ParseError):
        parse_and_solve("")


# -------------------------------------------------------------------------
# Flask endpoint tests (replaces old FastAPI versions)
# -------------------------------------------------------------------------
@pytest.fixture
def flask_client():
    from web.backend.main import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_ai_endpoint(flask_client):
    r = flask_client.post("/api/ai", json={"text": "add 5 and 3"})
    assert r.status_code == 200
    assert r.get_json()["result"] == 8


def test_ai_endpoint_bad_input(flask_client):
    r = flask_client.post("/api/ai", json={"text": "hello world"})
    assert r.status_code == 400


def test_ai_endpoint_empty(flask_client):
    r = flask_client.post("/api/ai", json={"text": ""})
    assert r.status_code == 400


def test_ai_status(flask_client):
    r = flask_client.get("/api/ai/status")
    assert r.status_code == 200
    data = r.get_json()
    assert "ai_available" in data
    assert data["ai_available"] is True
