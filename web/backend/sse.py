"""Server-Sent Events with backward-compatible API."""
from __future__ import annotations
import json
import queue
import threading
import time
import uuid
from collections import defaultdict

from flask import Blueprint, request, Response, jsonify

from .logging_config import get_logger
from .auth import require_auth

log = get_logger("web.sse")
sse_bp = Blueprint("sse", __name__, url_prefix="/api/events")

_SUBSCRIBERS = defaultdict(dict)
_LOCK = threading.Lock()
_HISTORY = defaultdict(list)
_MAX_HISTORY = 50


def subscribe(channel):
    sub_id = uuid.uuid4().hex
    q = queue.Queue(maxsize=100)
    with _LOCK:
        _SUBSCRIBERS[channel][sub_id] = q
    return sub_id, q


def unsubscribe(channel, sub_id):
    with _LOCK:
        _SUBSCRIBERS.get(channel, {}).pop(sub_id, None)


def broadcast(channel, event, data):
    payload = {"event": event, "data": data, "ts": time.time()}
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
    try:
        from .pubsub import get_backend
        b = get_backend()
        if b.name == "redis":
            b.publish(channel, event, data)
    except Exception:
        pass
    return delivered


def subscriber_count(channel):
    with _LOCK:
        return len(_SUBSCRIBERS.get(channel, {}))


@sse_bp.route("/stream", methods=["GET"])
def stream():
    channel = (request.args.get("channel") or "").strip()[:128]
    if not channel:
        return jsonify({"error": "channel is required"}), 400
    try:
        replay = min(int(request.args.get("replay", 0)), _MAX_HISTORY)
    except ValueError:
        replay = 0

    sub_id, q = subscribe(channel)

    def gen():
        try:
            yield ": connected\n\n"
            if replay > 0:
                with _LOCK:
                    for evt in _HISTORY.get(channel, [])[-replay:]:
                        yield f"event: {evt['event']}\n"
                        yield f"data: {json.dumps(evt['data'])}\n\n"
            while True:
                try:
                    evt = q.get(timeout=15)
                    yield f"event: {evt['event']}\n"
                    yield f"data: {json.dumps(evt['data'])}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            unsubscribe(channel, sub_id)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
               "Connection": "keep-alive"}
    return Response(gen(), mimetype="text/event-stream", headers=headers)


@sse_bp.route("/channels", methods=["GET"])
def channels():
    with _LOCK:
        out = {ch: len(subs) for ch, subs in _SUBSCRIBERS.items()}
    return jsonify({"channels": out})


@sse_bp.route("/pubsub/status", methods=["GET"])
def pubsub_status():
    try:
        from .pubsub import get_backend
        b = get_backend()
        name = b.name
        bchans = b.channels() if hasattr(b, "channels") else {}
    except Exception:
        name = "memory"; bchans = {}
    return jsonify({"backend": name, "channels": bchans})


@sse_bp.route("/broadcast", methods=["POST"])
@require_auth
def manual_broadcast():
    data = request.get_json(silent=True) or {}
    channel = (data.get("channel") or "").strip()[:128]
    event = (data.get("event") or "message").strip()[:64]
    payload = data.get("data") or {}
    if not channel:
        return jsonify({"error": "channel required"}), 400
    n = broadcast(channel, event, payload)
    return jsonify({"delivered": n, "channel": channel, "event": event})


def install_bridge():
    try:
        from .realtime import socketio

        @socketio.on("chat_message")
        def _relay_chat(data):
            try:
                d = data or {}
                if d.get("room"):
                    broadcast(f"room:{d['room']}", "chat_message", d)
            except Exception:
                pass

        @socketio.on("group_message")
        def _relay_group(data):
            try:
                d = data or {}
                if d.get("group_id"):
                    broadcast(f"group:{d['group_id']}", "group_message", d)
            except Exception:
                pass

        @socketio.on("user_status")
        def _relay_status(data):
            try:
                broadcast("status:global", "user_status", data or {})
            except Exception:
                pass
    except Exception:
        pass
