"""Tests for PWA routes (updated for Phase 22 modular frontend)."""


def test_manifest_served(client):
    r = client.get("/manifest.json")
    assert r.status_code == 200
    assert "application/manifest" in r.content_type
    data = r.get_json()
    assert data["name"] == "Arithmetic Super App"
    assert data["start_url"] == "/"
    assert data["display"] == "standalone"


def test_service_worker_served(client):
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert "javascript" in r.content_type
    assert r.headers.get("Service-Worker-Allowed") == "/"
    body = r.get_data(as_text=True)
    # Phase 28 bumped cache to v2
    assert "arith-pwa-v2" in body


def test_offline_page_served(client):
    r = client.get("/static/offline.html")
    assert r.status_code == 200
    assert b"You're offline" in r.data


def test_icons_served(client):
    for name in ("icon-192.svg", "icon-512.svg"):
        r = client.get(f"/static/{name}")
        assert r.status_code == 200
        assert b"<svg" in r.data


def test_index_html_has_manifest_link(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'rel="manifest"' in body


def test_index_html_loads_pwa_module(client):
    """Phase 22 moved SW registration into js/pwa.js."""
    r = client.get("/")
    body = r.get_data(as_text=True)
    assert "/static/js/pwa.js" in body


def test_pwa_module_registers_service_worker(client):
    r = client.get("/static/js/pwa.js")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "serviceWorker" in body
    assert "/sw.js" in body
