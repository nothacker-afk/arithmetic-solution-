"""Simple in-memory rate limiter (no external dependencies).

Suitable for a single-process dev/small deployment. For multi-worker
production use Redis-backed limits instead.
"""
import time
from collections import defaultdict
from functools import wraps

from flask import request, jsonify

# key -> list of request timestamps (epoch seconds)
_STORE: dict[str, list[float]] = defaultdict(list)


def reset() -> None:
    """Clear all rate-limit state (used in tests)."""
    _STORE.clear()


def rate_limit(max_calls: int = 60, window_seconds: int = 60):
    """Decorator: allow at most `max_calls` per `window_seconds` per IP.

    Returns HTTP 429 when exceeded.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = request.headers.get("X-Forwarded-For", request.remote_addr or "?")
            key = key.split(",")[0].strip()
            now = time.time()
            cutoff = now - window_seconds

            recent = [t for t in _STORE[key] if t > cutoff]
            if len(recent) >= max_calls:
                retry_after = int(recent[0] + window_seconds - now) + 1
                resp = jsonify({"error": "Rate limit exceeded. Try again later."})
                resp.headers["Retry-After"] = str(retry_after)
                return resp, 429

            recent.append(now)
            _STORE[key] = recent
            return f(*args, **kwargs)
        return wrapper
    return decorator
