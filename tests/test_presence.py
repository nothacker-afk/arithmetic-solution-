"""Tests for presence avatars (Phase 29)."""
from pathlib import Path

from web.backend.realtime import _user_color


def test_presence_js_exists():
    assert Path("web/frontend/js/presence.js").exists()


def test_presence_js_exports():
    src = Path("web/frontend/js/presence.js").read_text()
    for fn in ("colorOf", "initials", "avatarEl", "renderStrip", "init"):
        assert fn in src, f"missing export: {fn}"


def test_user_color_deterministic():
    assert _user_color("alice") == _user_color("alice")


def test_user_color_differs_between_users():
    assert _user_color("alice") != _user_color("bob")


def test_user_color_format():
    c = _user_color("charlie")
    assert c.startswith("hsl(")
    assert "%" in c


def test_user_color_handles_unicode():
    _user_color("café")
    _user_color("日本語")
    _user_color("")


def test_live_tab_js_exists():
    """The live tab module is where presence avatars are rendered."""
    assert Path("web/frontend/js/tabs/live.js").exists()
