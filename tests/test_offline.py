"""Tests for offline-first UI (Phase 28)."""
from pathlib import Path


def test_offline_js_exists():
    assert Path("web/frontend/js/offline.js").exists()


def test_offline_js_exports():
    src = Path("web/frontend/js/offline.js").read_text()
    for fn in ("cacheCalc", "listCalcs", "enqueue", "flushQueue",
               "setPref", "getPref", "init", "supported"):
        assert fn in src, f"missing export: {fn}"


def test_offline_uses_indexeddb():
    src = Path("web/frontend/js/offline.js").read_text()
    assert "indexedDB" in src
    assert "arith-offline" in src


def test_service_worker_precaches_new_modules():
    src = Path("web/frontend/sw.js").read_text()
    for asset in ("css/design.css", "js/api.js", "js/offline.js", "js/app.js"):
        assert asset in src, f"missing precache: {asset}"


def test_index_html_loads_offline_module():
    src = Path("web/frontend/index.html").read_text()
    assert "js/offline.js" in src


def test_basic_caches_result():
    src = Path("web/frontend/js/tabs/basic.js").read_text()
    assert "Offline.cacheCalc" in src


def test_history_falls_back_to_cache():
    src = Path("web/frontend/js/tabs/history.js").read_text()
    assert "Offline.listCalcs" in src
