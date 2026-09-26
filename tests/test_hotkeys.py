"""Static-analysis tests for hotkeys module (Phase 58)."""
from pathlib import Path


def test_hotkeys_file_exists():
    assert Path("web/frontend/js/hotkeys.js").exists()


def test_hotkeys_exports():
    src = Path("web/frontend/js/hotkeys.js").read_text()
    for name in ("init", "show", "effective", "DEFAULTS"):
        assert name in src


def test_hotkeys_loaded_in_index():
    src = Path("web/frontend/index.html").read_text()
    assert "js/hotkeys.js" in src
    assert 'id="hotkeys-help"' in src


def test_hotkeys_uses_localstorage():
    src = Path("web/frontend/js/hotkeys.js").read_text()
    assert "localStorage" in src
    assert "hotkeys.config" in src
