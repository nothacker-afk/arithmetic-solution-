"""Tests for the file-sharing API."""
import base64
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path, monkeypatch):
    """Every test gets its own file storage directory."""
    storage = tmp_path / "files"
    storage.mkdir()
    monkeypatch.setenv("FILE_STORAGE_DIR", str(storage))
    # Config reads env lazily? No — it's read at class creation. Patch the class.
    from web.backend import config
    monkeypatch.setattr(config.Config, "FILE_STORAGE_DIR", str(storage))
    yield storage


def _upload(client, room, filename, data: bytes, encrypted=True):
    return client.post(f"/api/files/{room}", json={
        "filename": filename,
        "ciphertext_b64": base64.b64encode(data).decode(),
        "encrypted": encrypted,
        "uploaded_by": "tester",
    })


def test_list_empty(client):
    r = client.get("/api/files/demo")
    assert r.status_code == 200
    body = r.get_json()
    assert body["files"] == []
    assert body["usage"]["count"] == 0


def test_upload_and_list(client):
    r = _upload(client, "demo", "hello.txt", b"ciphertext-here")
    assert r.status_code == 201
    file_id = r.get_json()["id"]

    r = client.get("/api/files/demo")
    files = r.get_json()["files"]
    assert len(files) == 1
    assert files[0]["filename"] == "hello.txt"
    assert files[0]["id"] == file_id


def test_download_returns_bytes(client):
    payload = b"\\x00\\x01\\x02 secret bytes"
    r = _upload(client, "demo", "blob.bin", payload)
    file_id = r.get_json()["id"]

    r = client.get(f"/api/files/demo/{file_id}")
    assert r.status_code == 200
    assert r.data == payload


def test_delete_file(client):
    r = _upload(client, "demo", "trash.txt", b"x")
    file_id = r.get_json()["id"]

    r = client.delete(f"/api/files/demo/{file_id}")
    assert r.status_code == 200
    assert client.get(f"/api/files/demo/{file_id}").status_code == 404


def test_clear_room(client):
    for i in range(3):
        _upload(client, "demo", f"f{i}.bin", b"x")
    r = client.delete("/api/files/demo")
    assert r.get_json()["deleted_count"] == 3
    assert client.get("/api/files/demo").get_json()["files"] == []


def test_invalid_room(client):
    assert client.get("/api/files/bad room").status_code == 400
    assert client.get("/api/files/bad!room").status_code == 400


def test_invalid_file_id(client):
    assert client.get("/api/files/demo/not-hex").status_code == 400


def test_missing_file(client):
    fake = "a" * 32
    assert client.get(f"/api/files/demo/{fake}").status_code == 404


def test_missing_ciphertext(client):
    r = client.post("/api/files/demo", json={"filename": "x.txt"})
    assert r.status_code == 400


def test_invalid_base64(client):
    r = client.post("/api/files/demo", json={
        "filename": "x.txt",
        "ciphertext_b64": "!!!not-base64!!!",
    })
    assert r.status_code == 400


def test_filename_sanitization(client):
    r = _upload(client, "demo", "../../etc/passwd", b"x")
    assert r.status_code == 201
    # Filename should be sanitized — no path components
    assert "/" not in r.get_json()["filename"]
    assert ".." not in r.get_json()["filename"]


def test_file_size_limit(client, monkeypatch):
    from web.backend import config
    monkeypatch.setattr(config.Config, "MAX_FILE_SIZE_MB", 0)  # 0 MB → reject anything
    r = _upload(client, "demo", "big.bin", b"x" * 100)
    assert r.status_code == 413


def test_file_count_limit(client, monkeypatch):
    from web.backend import config
    monkeypatch.setattr(config.Config, "MAX_FILES_PER_ROOM", 2)
    _upload(client, "demo", "a", b"x")
    _upload(client, "demo", "b", b"x")
    r = _upload(client, "demo", "c", b"x")
    assert r.status_code == 413


def test_rooms_isolated(client):
    _upload(client, "room-a", "a.txt", b"aaa")
    _upload(client, "room-b", "b.txt", b"bbb")
    a = client.get("/api/files/room-a").get_json()["files"]
    b = client.get("/api/files/room-b").get_json()["files"]
    assert len(a) == 1 and a[0]["filename"] == "a.txt"
    assert len(b) == 1 and b[0]["filename"] == "b.txt"


def test_usage_tracked(client):
    _upload(client, "demo", "a", b"x" * 100)
    _upload(client, "demo", "b", b"y" * 200)
    usage = client.get("/api/files/demo").get_json()["usage"]
    assert usage["count"] == 2
    assert usage["total_bytes"] == 300
