"""Server-Sent Events fallback (Phase 63).

Provides a long-poll / SSE alternative for clients that can't use
WebSockets (some proxies, older browsers, restrictive firewalls).

Design:
  - In-process subscriber registry keyed by channel name
  - `broadcast(channel, event, data)` called by other modules
  - `/api/events/stream?channel=X` yields newline-delimited SSE events
  - `/api/events/broadcast` (admin only) for testing
  - Auto-cleanup on client disconnect

This is best-effort: multi-process deployments need Redis pub/sub or
similar. For single-process dev/small deployments it's sufficient.
"""
import json
import queue
import threading
import time
import uuid
from collections import defaultdict

from flask import Blueprint, request, Response, jsonify, g

from .auth import require_auth
from .rate_limit import rate_limit

sse_bp = Blueprint("sse", __name__, url_prefix="/api/events")

# channel -> { subscriber_id -> queue.Queue }
_SUBSCRIBERS: dict[str, dict[str, "queue.Queue"]] = defaultdict(dict)
_LOCK = threading.Lock()

# Event log for replay on connect (bounded per channel)
_HISTORY: dict[str, list[dict]] = defaultdict(list)
_MAX_HISTORY = 50


def subscribe(channel: str) -> tuple[str, "queue.Queue"]:
    sub_id = uuid.uuid4().hex
    q: "queue.Queue" = queue.Queue(maxsize=100)
    with _LOCK:
        _SUBSCRIBERS[channel][sub_id] = q
    return sub_id, q


def unsubscribe(channel: str, sub_id: str) -> None:
    with _LOCK:
        _SUBSCRIBERS.get(channel, {}).pop(sub_id, None)


def broadcast(channel: str, event: str, data: dict) -> int:
    """Send an event to all subscribers of a channel. Returns delivery count."""
    payload = {"event": event, "data": data, "ts": time.time()}
    # Store history
    with _LOCK:
        hist = _HISTORY[channel]
        hist.append(payload)
        if len(hist) > _MAX_HISTORY:
            del hist[:-_MAX_HISTORY]

        subs = list(_SUBSCRIBERS.get(channel, {}).values())

    delivered = 0
    for q in subs:
        try:
            q.put_nowait(payload)
            delivered += 1
        except queue.Full:
            pass
    return delivered


def subscriber_count(channel: str) -> int:
    with _LOCK:
        return len(_SUBSCRIBERS.get(channel, {}))


@sse_bp.route("/stream", methods=["GET"])
def stream():
    """SSE stream. Channel is required.

    Note: this endpoint is intentionally unauthenticated to allow
    public room streaming. Sensitive channels (e.g. per-user events)
    should include a shared secret in the channel name.
    """
    channel = (request.args.get("channel") or "").strip()[:128]
    if not channel:
        return jsonify({"error": "channel is required"}), 400

    # Optional replay of last N events
    try:
        replay = min(int(request.args.get("replay", 0)), _MAX_HISTORY)
    except ValueError:
        replay = 0

    sub_id, q = subscribe(channel)

    def gen():
        try:
            # Initial comment keeps some proxies from buffering
            yield ": connected\n\n"

            # Replay history if requested
            if replay > 0:
                with _LOCK:
                    for evt in _HISTORY.get(channel, [])[-replay:]:
                        yield f"event: {evt['event']}\n"
                        yield f"data: {json.dumps(evt['data'])}\n\n"

            last_heartbeat = time.time()
            while True:
                try:
                    evt = q.get(timeout=15)
                    yield f"event: {evt['event']}\n"
                    yield f"data: {json.dumps(evt['data'])}\n\n"
                except queue.Empty:
                    # Heartbeat every 15s keeps connection alive
                    yield ": heartbeat\n\n"
                last_heartbeat = time.time()
        except GeneratorExit:
            pass
        finally:
            unsubscribe(channel, sub_id)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(gen(), mimetype="text/event-stream", headers=headers)


@sse_bp.route("/channels", methods=["GET"])
def channels():
    """List active channels and subscriber counts (for diagnostics)."""
    with _LOCK:
        out = {ch: len(subs) for ch, subs in _SUBSCRIBERS.items()}
    return jsonify({"channels": out})


@sse_bp.route("/broadcast", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def manual_broadcast():
    """Manually broadcast (handy for testing). Auth required."""
    data = request.get_json(silent=True) or {}
    channel = (data.get("channel") or "").strip()[:128]
    event = (data.get("event") or "message").strip()[:64]
    payload = data.get("data") or {}
    if not channel:
        return jsonify({"error": "channel required"}), 400
    n = broadcast(channel, event, payload)
    return jsonify({"delivered": n, "channel": channel, "event": event})


# ---------------------------------------------------------------------
# Bridging from realtime socketio events to SSE
# ---------------------------------------------------------------------
def _bridge_from_socketio_event(event_name: str, channel_builder):
    """Register a socketio listener that mirrors the event to SSE."""
    try:
        from .realtime import socketio

        @socketio.on(event_name)
        def _handler(data):  # noqa: F811
            try:
                ch = channel_builder(data or {})
                if ch:
                    broadcast(ch, event_name, data or {})
            except Exception:
                pass

        return True
    except Exception:
        return False


def install_bridge() -> None:
    """Bridge common socketio events to SSE channels."""
    _bridge_from_socketio_event("chat_message",
        lambda d: f"room:{d.get('room')}" if d.get("room") else None)
    _bridge_from_socketio_event("group_message",
        lambda d: f"group:{d.get('group_id')}" if d.get("group_id") else None)
    _bridge_from_socketio_event("user_status",
        lambda d: "status:global")
