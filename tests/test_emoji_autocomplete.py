"""Static-analysis tests for emoji autocomplete (Phase 36)."""
from pathlib import Path


def test_module_exists():
    assert Path("web/frontend/js/emoji_autocomplete.js").exists()


def test_module_exports():
    src = Path("web/frontend/js/emoji_autocomplete.js").read_text()
    for fn in ("init", "attach", "SHORTCODES", "palette"):
        assert fn in src


def test_shortcodes_include_common():
    src = Path("web/frontend/js/emoji_autocomplete.js").read_text()
    for code in ("smile", "heart", "fire", "tada", "rocket"):
        assert f'"{code}"' in src


def test_index_loads_module():
    src = Path("web/frontend/index.html").read_text()
    assert "emoji_autocomplete.js" in src


def test_css_present():
    src = Path("web/frontend/css/chat-addons.css").read_text()
    assert ".emoji-autocomplete" in src
