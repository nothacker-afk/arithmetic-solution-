"""Static-analysis tests for the Flet mobile client (Phase 71)."""
from pathlib import Path


def test_mobile_file_exists():
    assert Path("mobile/app.py").exists()


def test_mobile_has_all_tabs():
    src = Path("mobile/app.py").read_text()
    for tab in ("calc", "live", "dms", "groups", "search", "contacts", "auth"):
        assert tab in src, f"missing tab: {tab}"


def test_mobile_uses_backend_endpoints():
    src = Path("mobile/app.py").read_text()
    for endpoint in ("/api/auth/register", "/api/auth/login",
                     "/api/basic", "/api/scientific", "/api/ai",
                     "/api/chat/", "/api/dms/threads", "/api/groups",
                     "/api/search", "/api/contacts"):
        assert endpoint in src, f"missing endpoint: {endpoint}"


def test_mobile_has_required_imports():
    src = Path("mobile/app.py").read_text()
    assert "import flet" in src
    assert "import requests" in src
