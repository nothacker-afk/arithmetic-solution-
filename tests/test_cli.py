"""Tests for CLI integration with the core engine."""
import json
import subprocess
import sys
from pathlib import Path


def test_cli_imports():
    """CLI module should import without errors."""
    import cli.main  # noqa: F401


def test_cli_quit(tmp_path, monkeypatch):
    """Sending 'q' to the CLI should exit cleanly."""
    monkeypatch.setenv("HOME", str(tmp_path))
    result = subprocess.run(
        [sys.executable, "-m", "cli.main"],
        input="q\n",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "Goodbye" in result.stderr


def test_cli_basic_addition(tmp_path, monkeypatch):
    """Simulate: choose basic add, a=2, b=3, then quit."""
    monkeypatch.setenv("HOME", str(tmp_path))
    result = subprocess.run(
        [sys.executable, "-m", "cli.main"],
        input="1\n1\n2\n3\nq\n",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert "2.0 + 3.0 = 5.0" in result.stderr
