"""Tests for the component gallery (Phase 27)."""
from pathlib import Path


def test_gallery_file_exists():
    assert Path("web/frontend/gallery.html").exists()


def test_gallery_has_all_component_sections():
    src = Path("web/frontend/gallery.html").read_text()
    for section in ("Colors", "Typography", "Buttons", "Form fields",
                    "Tabs", "Cards", "Result panel", "Badges",
                    "Chat log", "Feed items", "Skeletons",
                    "Empty state", "Toasts", "Modal"):
        assert section in src, f"missing section: {section}"


def test_gallery_route(client):
    r = client.get("/gallery")
    assert r.status_code == 200
    assert b"Component Gallery" in r.data


def test_gallery_links_design_css():
    src = Path("web/frontend/gallery.html").read_text()
    assert "/static/css/design.css" in src
    assert "/static/css/components.css" in src
