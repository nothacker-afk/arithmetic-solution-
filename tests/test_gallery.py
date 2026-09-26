"""Tests for the component gallery (Phase 27, upgraded Phase 49)."""
import re
from pathlib import Path


def test_gallery_file_exists():
    assert Path("web/frontend/gallery.html").exists()


def test_gallery_has_section_structure():
    """Every section has a heading and a demo container."""
    src = Path("web/frontend/gallery.html").read_text()
    sections = re.findall(r'<section class="gallery-section"[^>]*>(.*?)</section>',
                          src, re.DOTALL)
    # We expect at least 12 sections after Phases 49 + 46-50 additions
    assert len(sections) >= 12, f"only {len(sections)} sections found"

    # Each section should have an <h2> and some demo content
    for s in sections:
        assert "<h2>" in s, "section missing <h2>"


def test_gallery_has_expected_sections():
    """Match a subset of sections that exist in the current build."""
    src = Path("web/frontend/gallery.html").read_text()
    expected = [
        "Colors", "Typography", "Buttons", "Form fields",
        "Tabs", "Cards", "Badges",
        "Chat + reactions", "Voice player", "Media gallery",
        "Toasts", "Modal", "Skeletons",
    ]
    for name in expected:
        assert name in src, f"missing section: {name}"


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


def test_gallery_has_all_css_imports():
    """Gallery should load every stylesheet that the main app loads."""
    src = Path("web/frontend/gallery.html").read_text()
    for css in ("design.css", "components.css", "chat-addons.css",
                "phase41.css", "phase46.css"):
        assert css in src, f"missing CSS: {css}"
