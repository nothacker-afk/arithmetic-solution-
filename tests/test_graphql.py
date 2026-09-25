"""Tests for the GraphQL API."""
import pytest


def _gql(client, query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    r = client.post("/graphql", json=payload)
    return r


def test_graphql_health(client):
    r = _gql(client, "{ health }")
    assert r.status_code == 200
    assert r.get_json()["data"]["health"] == "ok"


def test_graphql_version(client):
    r = _gql(client, "{ version }")
    assert r.get_json()["data"]["version"] == "0.8.0"


def test_graphql_plugins(client):
    r = _gql(client, "{ plugins { name arity } }")
    names = [p["name"] for p in r.get_json()["data"]["plugins"]]
    assert "gcd" in names
    assert "lcm" in names


def test_graphql_basic_as_query(client):
    r = _gql(client, '{ basic(operation: "add", a: 5, b: 3) { expression result } }')
    data = r.get_json()["data"]["basic"]
    assert data["result"] == "8"


def test_graphql_basic_mutation(client):
    r = _gql(client, 'mutation { basic(operation: "multiply", a: 4, b: 7) { expression result } }')
    data = r.get_json()["data"]["basic"]
    assert data["result"] == "28"


def test_graphql_scientific(client):
    r = _gql(client, 'mutation { scientific(operation: "sqrt", x: 144) { result } }')
    data = r.get_json()["data"]["scientific"]
    assert data["result"] == "12.0"


def test_graphql_matrix(client):
    query = '''
    mutation {
      matrix(
        operation: "matrix_multiply"
        a: [[1, 2], [3, 4]]
        b: [[5, 6], [7, 8]]
      ) { expression result }
    }
    '''
    r = _gql(client, query)
    data = r.get_json()["data"]["matrix"]
    assert "[[19, 22], [43, 50]]" in data["result"]


def test_graphql_plugin_call(client):
    r = _gql(client, 'mutation { callPlugin(name: "gcd", args: [12, 18]) { result } }')
    data = r.get_json()["data"]["callPlugin"]
    assert data["result"] == "6"


def test_graphql_ai(client):
    r = _gql(client, 'mutation { aiSolve(text: "add 5 and 3") { result expression } }')
    data = r.get_json()["data"]["aiSolve"]
    assert data["result"] == "8"


def test_graphql_unknown_op_returns_error(client):
    r = _gql(client, 'mutation { basic(operation: "wat", a: 1, b: 1) { result } }')
    body = r.get_json()
    assert "errors" in body
    assert body["data"]["basic"] is None


def test_graphql_introspection(client):
    r = _gql(client, "{ __schema { queryType { name } mutationType { name } } }")
    schema_info = r.get_json()["data"]["__schema"]
    assert schema_info["queryType"]["name"] == "Query"
    assert schema_info["mutationType"]["name"] == "Mutation"
