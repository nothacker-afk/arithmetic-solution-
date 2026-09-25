"""Tests for the Flask web backend."""
import pytest
from web.backend.main import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"
    assert r.get_json()["backend"] == "flask"


def test_basic_add(client):
    r = client.post("/api/basic", json={"operation": "add", "a": 10, "b": 5})
    assert r.status_code == 200
    assert r.get_json()["result"] == 15


def test_basic_divide_by_zero(client):
    r = client.post("/api/basic", json={"operation": "divide", "a": 1, "b": 0})
    assert r.status_code == 400


def test_basic_unknown_op(client):
    r = client.post("/api/basic", json={"operation": "wat", "a": 1, "b": 1})
    assert r.status_code == 400


def test_scientific_sqrt(client):
    r = client.post("/api/scientific", json={"operation": "sqrt", "x": 144})
    assert r.status_code == 200
    assert r.get_json()["result"] == 12.0


def test_scientific_sqrt_negative(client):
    r = client.post("/api/scientific", json={"operation": "sqrt", "x": -1})
    assert r.status_code == 400


def test_matrix_multiply(client):
    r = client.post("/api/matrix", json={
        "operation": "matrix_multiply",
        "a": [[1, 2], [3, 4]],
        "b": [[5, 6], [7, 8]],
    })
    assert r.status_code == 200
    assert r.get_json()["result"] == [[19, 22], [43, 50]]


def test_matrix_transpose(client):
    r = client.post("/api/matrix", json={
        "operation": "matrix_transpose",
        "a": [[1, 2], [3, 4]],
    })
    assert r.status_code == 200
    assert r.get_json()["result"] == [[1, 3], [2, 4]]


def test_ai_endpoint(client):
    """AI endpoint may return 503 if Phase 3 not yet installed."""
    r = client.post("/api/ai", json={"text": "add 5 and 3"})
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.get_json()["result"] == 8


def test_ai_endpoint_bad_input(client):
    r = client.post("/api/ai", json={"text": "hello world"})
    assert r.status_code in (400, 503)
