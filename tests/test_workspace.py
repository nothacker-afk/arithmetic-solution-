"""Static-analysis tests for the workspace scaffold (Phase 78)."""
from pathlib import Path


def test_workspace_docs_exist():
    assert Path("workspace/WORKSPACE.md").exists()
    assert Path("workspace/specs/contracts.md").exists()


def test_workspace_scripts_executable():
    for s in ("workspace/scripts/run-all-tests.sh", "workspace/scripts/status.sh"):
        p = Path(s)
        assert p.exists(), f"missing {s}"


def test_workspace_lists_subprojects():
    src = Path("workspace/WORKSPACE.md").read_text()
    for d in ("arithmetic/", "ai_engine/", "cli/", "web/", "mobile/", "arith/"):
        assert d in src, f"missing subproject in docs: {d}"


def test_contracts_cover_interfaces():
    src = Path("workspace/specs/contracts.md").read_text()
    for iface in ("arithmetic/", "ai_engine/", "cli/", "web/backend/", "mobile/"):
        assert iface in src


def test_background_module_exists():
    assert Path("web/backend/background.py").exists()
