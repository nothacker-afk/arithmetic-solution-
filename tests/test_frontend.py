"""Static-analysis tests for the rebuilt frontend (Phases 22-23)."""
from pathlib import Path


def test_design_css_exists():
    css = Path("web/frontend/css/design.css")
    assert css.exists()
    src = css.read_text()
    for token in ("--bg-0", "--accent", "--radius", "--dur", "prefers-reduced-motion"):
        assert token in src, f"missing token: {token}"


def test_components_css_exists():
    css = Path("web/frontend/css/components.css")
    assert css.exists()
    src = css.read_text()
    for component in (".btn", ".card", ".tabs", ".toast", ".cmdk", ".skeleton"):
        assert component in src, f"missing component: {component}"


def test_js_modules_present():
    files = [
        "web/frontend/js/api.js",
        "web/frontend/js/ui.js",
        "web/frontend/js/theme.js",
        "web/frontend/js/i18n_client.js",
        "web/frontend/js/commands.js",
        "web/frontend/js/app.js",
        "web/frontend/js/pwa.js",
        "web/frontend/js/tabs/basic.js",
        "web/frontend/js/tabs/scientific.js",
        "web/frontend/js/tabs/matrix.js",
        "web/frontend/js/tabs/ai.js",
        "web/frontend/js/tabs/history.js",
        "web/frontend/js/tabs/live.js",
    ]
    for f in files:
        assert Path(f).exists(), f"missing {f}"


def test_index_html_references_all_modules():
    src = Path("web/frontend/index.html").read_text()
    for ref in ("css/design.css", "css/components.css", "js/api.js",
                "js/ui.js", "js/theme.js", "js/commands.js", "js/app.js",
                "js/tabs/basic.js", "js/tabs/live.js"):
        assert ref in src, f"missing reference: {ref}"


def test_index_html_has_skip_link():
    src = Path("web/frontend/index.html").read_text()
    assert "skip-link" in src
    assert 'href="#main"' in src


def test_index_html_has_no_inline_style():
    """The rebuilt index.html should not have inline <style> blocks."""
    src = Path("web/frontend/index.html").read_text()
    assert "<style>" not in src, "found inline <style> — CSS should be in css/"
