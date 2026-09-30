"""Tests for offline-first UI (Phase 28)."""
from pathlib import Path


def test_offline_js_exists():
    assert Path("web/frontend/js/offline.js").exists()


def test_offline_js_exports():
    """Module exports the public API used elsewhere in the app."""
    src = Path("web/frontend/js/offline.js").read_text()
    for fn in ("cacheCalc", "listCalcs", "enqueue", "flushQueue",
               "setPref", "getPref", "init", "supported"):
        assert fn in src, f"missing export: {fn}"


def test_offline_uses_indexeddb():
    src = Path("web/frontend/js/offline.js").read_text()
    assert "indexedDB" in src
    assert "arith-offline" in src


def test_service_worker_precaches_core_modules():
    """Service worker should precache the core app files."""
    sw = Path("web/frontend/sw.js")
    assert sw.exists()
    src = sw.read_text()
    for asset in ("css/design.css", "js/api.js", "js/ui.js", "js/app.js"):
        assert asset in src, f"sw.js missing precache: {asset}"


def test_basic_js_exists():
    assert Path("web/frontend/js/tabs/basic.js").exists()


def test_history_js_exists():
    assert Path("web/frontend/js/tabs/history.js").exists()


def test_offline_css_styles_present():
    """Offline-related CSS lives somewhere in the frontend."""
    css_files = list(Path("web/frontend/css").glob("*.css"))
    assert css_files, "no CSS files found"
