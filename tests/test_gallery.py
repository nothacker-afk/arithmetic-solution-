"""Tests for the component gallery (Phase 27, upgraded Phase 49)."""
from pathlib import Path


def test_gallery_file_exists():
    assert Path("web/frontend/gallery.html").exists()


def test_gallery_has_all_component_sections():
    """Check for section headings that exist in the current gallery."""
    src = Path("web/frontend/gallery.html").read_text()
    for section in (
        "Colors", "Typography", "Buttons", "Form fields",
        "Tabs", "Cards", "Badges", "Result panel",
        "Chat + reactions", "Voice player", "Media gallery",
        "Chips", "Toasts", "Modal", "Skeletons",
        "Empty state", "Sync indicators",
    ):
        assert section in src, f"missing section: {section}"


def test_gallery_route(client):
    r = client.get("/gallery")
    assert r.status_code == 200
    assert b"Component Gallery" in r.data


def test_gallery_links_design_css():
    src = Path("web/frontend/gallery.html").read_text()
    assert "/static/css/design.css" in src
    assert "/static/css/components.css" in src


def test_gallery_has_sidebar_nav():
    """Phase 49 added a Storybook-style sidebar."""
    src = Path("web/frontend/gallery.html").read_text()
    assert "gallery-nav" in src
    assert "IntersectionObserver" in src


def test_gallery_has_copy_buttons():
    """Phase 49 added copy-to-clipboard for code samples."""
    src = Path("web/frontend/gallery.html").read_text()
    assert "gallery-copy" in src
    assert "clipboard" in src.lower()
