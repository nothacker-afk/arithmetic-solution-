"""Tests for LLM fallback behavior (no real API calls)."""
from unittest.mock import patch

from ai_engine.llm import llm_solve, is_llm_available
from ai_engine.parser import parse_and_solve


def test_llm_unavailable_falls_back(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert is_llm_available() is False
    r = llm_solve("add 5 and 3")
    assert r["result"] == 8


def test_llm_api_error_falls_back(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    # Force openai import to work but call to raise
    with patch("ai_engine.llm.OpenAI", side_effect=RuntimeError("network down")):
        r = llm_solve("add 5 and 3")
        assert r["result"] == 8


def test_llm_openai_import_missing(monkeypatch):
    """If openai package is not installed, fall back cleanly."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")

    # Simulate ImportError inside llm_solve
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("simulated missing openai")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        r = llm_solve("square root of 81")
        assert r["result"] == 9.0


def test_rule_parser_still_works():
    """Sanity: the underlying parser works independently."""
    r = parse_and_solve("what is 15% of 240")
    assert r["result"] == 36.0
