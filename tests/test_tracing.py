"""Tests for OpenTelemetry tracing (Phase 21)."""
import importlib

import pytest


def _reload_tracing():
    """Reload module so module-level state resets between tests."""
    from web.backend import tracing
    importlib.reload(tracing)
    return tracing


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    tracing = _reload_tracing()
    assert tracing.is_enabled() is False
    assert tracing.setup_tracing() is False
    assert tracing.current_trace_id() is None


def test_disabled_when_env_unset(monkeypatch):
    monkeypatch.setenv("OTEL_ENABLED", "")
    tracing = _reload_tracing()
    assert tracing.is_enabled() is False


def test_enabled_flag_parsing(monkeypatch):
    tracing = _reload_tracing()
    for val in ("1", "true", "TRUE", "yes", "on", "Yes"):
        monkeypatch.setenv("OTEL_ENABLED", val)
        assert tracing.is_enabled() is True
    for val in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("OTEL_ENABLED", val)
        assert tracing.is_enabled() is False


def test_trace_decorator_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    tracing = _reload_tracing()

    @tracing.trace("my.span")
    def add(a, b):
        return a + b

    # Should just call through, no error
    assert add(2, 3) == 5


def test_trace_decorator_preserves_exceptions(monkeypatch):
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    tracing = _reload_tracing()

    @tracing.trace()
    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        boom()


def test_setup_tracing_when_sdk_missing(monkeypatch):
    """If OTel SDK isn't installed, setup returns False without raising."""
    monkeypatch.setenv("OTEL_ENABLED", "1")
    tracing = _reload_tracing()
    result = tracing.setup_tracing()
    # Either True (SDK present) or False (SDK missing) — must not raise
    assert isinstance(result, bool)


def test_shutdown_is_safe(monkeypatch):
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    tracing = _reload_tracing()
    tracing.shutdown()  # no-op
