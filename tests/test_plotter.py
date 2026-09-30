"""Static tests for function plotter (Phase 90)."""
from pathlib import Path


def test_plotter_js_exists():
    assert Path("web/frontend/js/plotter.js").exists()


def test_plotter_exports():
    src = Path("web/frontend/js/plotter.js").read_text()
    assert "open" in src


def test_plotter_uses_canvas():
    src = Path("web/frontend/js/plotter.js").read_text()
    assert "canvas" in src
    assert "getContext" in src


def test_index_loads_plotter():
    src = Path("web/frontend/index.html").read_text()
    assert "js/plotter.js" in src


def test_index_loads_solver():
    src = Path("web/frontend/index.html").read_text()
    assert "js/solver.js" in src
