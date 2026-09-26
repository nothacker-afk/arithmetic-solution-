"""Tests for presence avatars (Phase 29)."""
from pathlib import Path

from web.backend.realtime import _user_color


def test_presence_js_exists():
    assert Path("web/frontend/js/presence.js").exists()


def test_presence_js_exports():
    src = Path("web/frontend/js/presence.js").read_text()
    for fn in ("colorOf", "initials", "avatarEl", "renderStrip", "init"):
        assert fn in src, f"missing export: {fn}"


def test_user_color_is_deterministic():
    a1 = _user_color("alice")
    a2 = _user_color("alice")
    assert a1 == a2


def test_user_color_differs_between_users():
    assert _user_color("alice") != _user_color("bob")


def test_user_color_format():
    c = _user_color("charlie")
    assert c.startswith("hsl(")
    assert "%" in c


def test_user_color_handles_unicode():
    # Must not crash on non-ascii
    _user_color("café")
    _user_color("日本語")
    _user_color("")


def test_index_html_has_presence_strip():
    src = Path("web/frontend/index.html").read_text()
    assert 'id="rt-avatars"' in src
    assert "js/presence.js" in src


def test_live_tab_renders_avatars():
    src = Path("web/frontend/js/tabs/live.js").read_text()
    assert "Presence.renderStrip" in src
