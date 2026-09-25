"""Request ID propagation, structured logging, and metrics."""
import time
import uuid
from collections import defaultdict
from threading import Lock

from flask import request, g

from .logging_config import get_logger

log = get_logger("web.middleware")


class Metrics:
    def __init__(self):
        self._lock = Lock()
        self.requests_total = defaultdict(int)
        self.request_duration_sum = defaultdict(float)
        self.request_duration_count = defaultdict(int)
        self.errors_total = defaultdict(int)
        self.start_time = time.time()

    def record(self, method, path, status, duration):
        with self._lock:
            self.requests_total[(method, path, status)] += 1
            self.request_duration_sum[(method, path)] += duration
            self.request_duration_count[(method, path)] += 1
            if status >= 500:
                self.errors_total[status] += 1

    def uptime_seconds(self):
        return time.time() - self.start_time

    def reset(self):
        with self._lock:
            self.requests_total.clear()
            self.request_duration_sum.clear()
            self.request_duration_count.clear()
            self.errors_total.clear()
            self.start_time = time.time()

    def render_prometheus(self) -> str:
        lines = []
        lines.append("# HELP arithmetic_uptime_seconds Process uptime")
        lines.append("# TYPE arithmetic_uptime_seconds gauge")
        lines.append(f"arithmetic_uptime_seconds {self.uptime_seconds():.3f}")

        lines.append("# HELP arithmetic_requests_total Total HTTP requests")
        lines.append("# TYPE arithmetic_requests_total counter")
        for (method, path, status), count in sorted(self.requests_total.items()):
            safe = path.replace('"', '\\"')
            lines.append(f'arithmetic_requests_total{{method="{method}",path="{safe}",status="{status}"}} {count}')

        lines.append("# HELP arithmetic_request_duration_seconds_sum Sum of request durations")
        lines.append("# TYPE arithmetic_request_duration_seconds_sum counter")
        for (method, path), total in sorted(self.request_duration_sum.items()):
            safe = path.replace('"', '\\"')
            lines.append(f'arithmetic_request_duration_seconds_sum{{method="{method}",path="{safe}"}} {total:.6f}')

        lines.append("# HELP arithmetic_request_duration_seconds_count Count of requests")
        lines.append("# TYPE arithmetic_request_duration_seconds_count counter")
        for (method, path), count in sorted(self.request_duration_count.items()):
            safe = path.replace('"', '\\"')
            lines.append(f'arithmetic_request_duration_seconds_count{{method="{method}",path="{safe}"}} {count}')

        lines.append("# HELP arithmetic_errors_total Total 5xx responses")
        lines.append("# TYPE arithmetic_errors_total counter")
        for status, count in sorted(self.errors_total.items()):
            lines.append(f'arithmetic_errors_total{{status="{status}"}} {count}')
        return "\n".join(lines) + "\n"


METRICS = Metrics()


def _path_template():
    if request.url_rule is not None:
        return request.url_rule.rule
    return request.path


def install_middleware(app) -> None:
    @app.before_request
    def _start_timer():
        g._start_time = time.time()
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]

    @app.after_request
    def _log_and_measure(response):
        duration = time.time() - getattr(g, "_start_time", time.time())
        path = _path_template()
        METRICS.record(request.method, path, response.status_code, duration)
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        if path not in ("/api/health", "/metrics"):
            log.info("request", extra={
                "request_id": getattr(g, "request_id", ""),
                "method": request.method,
                "path": path,
                "status": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            })
        return response
