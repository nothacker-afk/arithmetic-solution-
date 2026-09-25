"""OpenTelemetry tracing (Phase 21).

Enabled only when OTEL_ENABLED=1 (or true/yes). Safe to import and call
even without the OTel packages installed — every function degrades to a
no-op.

Environment:
    OTEL_ENABLED                    1/true/yes → enable tracing
    OTEL_SERVICE_NAME               (default: arithmetic-super-app)
    OTEL_EXPORTER_OTLP_ENDPOINT     HTTP endpoint (optional)
                                    e.g. http://localhost:4318/v1/traces
    OTEL_TRACES_SAMPLER_ARG         sample ratio 0..1 (default 1.0)
"""
import functools
import os
from typing import Optional

from .logging_config import get_logger

log = get_logger("web.tracing")

_tracer = None
_initialized = False


def is_enabled() -> bool:
    return os.environ.get("OTEL_ENABLED", "").lower() in ("1", "true", "yes", "on")


def setup_tracing(app=None) -> bool:
    """Configure a TracerProvider and optionally instrument Flask.

    Returns True if tracing was successfully enabled, False otherwise.
    """
    global _tracer, _initialized
    if _initialized:
        return _tracer is not None
    _initialized = True

    if not is_enabled():
        log.info("tracing disabled (set OTEL_ENABLED=1 to enable)")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except ImportError as e:
        log.warning("opentelemetry SDK not installed (%s) — tracing disabled", e)
        return False

    service_name = os.environ.get("OTEL_SERVICE_NAME", "arithmetic-super-app")
    try:
        ratio = float(os.environ.get("OTEL_TRACES_SAMPLER_ARG", "1.0"))
    except ValueError:
        ratio = 1.0
    sampler = TraceIdRatioBased(max(0.0, min(1.0, ratio)))

    resource = Resource.create({
        "service.name": service_name,
        "service.version": "0.21.0",
    })
    provider = TracerProvider(resource=resource, sampler=sampler)

    # Console exporter by default if no OTLP endpoint is set
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            log.info("OTLP exporter configured: %s", endpoint)
        except ImportError:
            log.warning("OTLP exporter package missing; falling back to console")
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        log.info("tracing enabled (console exporter)")

    trace.set_tracer_provider(provider)

    if app is not None:
        try:
            from opentelemetry.instrumentation.flask import FlaskInstrumentor
            FlaskInstrumentor().instrument_app(app)
            log.info("Flask auto-instrumentation enabled")
        except ImportError:
            log.warning("opentelemetry-instrumentation-flask not installed")

    _tracer = trace.get_tracer("arithmetic")
    return True


def trace(name: Optional[str] = None):
    """Decorator: wrap a function in an OTel span. No-op if tracing is off."""
    def decorator(f):
        span_name = name or f"{f.__module__}.{f.__name__}"

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if _tracer is None:
                return f(*args, **kwargs)
            with _tracer.start_as_current_span(span_name) as span:
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    span.record_exception(e)
                    raise
        return wrapper
    return decorator


def current_trace_id() -> Optional[str]:
    """Return the current W3C trace id as 32 hex chars, or None."""
    if _tracer is None:
        return None
    try:
        from opentelemetry import trace
        ctx = trace.get_current_span().get_span_context()
        if ctx and ctx.is_valid:
            return format(ctx.trace_id, "032x")
    except Exception:
        pass
    return None


def shutdown() -> None:
    """Flush pending spans (call on app shutdown)."""
    if _tracer is None:
        return
    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except Exception:
        pass
