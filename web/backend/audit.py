"""Audit logging (Phase 13).

Records auth events and room-admin actions. Never raises — logging
failure must not break the request.
"""
import json
from typing import Any, Optional

from flask import request, has_request_context

from .database import get_db
from .logging_config import get_logger

log = get_logger("web.audit")


def log_event(
    action: str,
    actor_id: Optional[int] = None,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    status: str = "ok",
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Insert an audit row. Safe to call from anywhere, even outside a request."""
    ip = None
    ua = None
    if has_request_context():
        ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:64]
        ua = (request.headers.get("User-Agent") or "")[:200]

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO audit_log "
                "(action, actor_id, resource, resource_id, status, details, ip, user_agent) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    action,
                    actor_id,
                    resource,
                    resource_id,
                    status,
                    json.dumps(details) if details else None,
                    ip,
                    ua,
                ),
            )
    except Exception as e:  # noqa: BLE001
        log.warning("audit insert failed: %s", e)
