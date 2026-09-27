"""Pub/Sub abstraction (Phase 69).

Provides a unified interface over two backends:
    - MemoryBackend: in-process, single-worker (default)
    - RedisBackend: cross-worker, requires `redis` package + REDIS_URL

Backends are chosen by `get_backend()` based on env vars. Callers
never touch a specific backend directly.

Usage:
    from .pubsub import get_backend
    backend = get_backend()
    backend.publish("room:demo", "chat_message", {"body": "hi"})
    sub = backend.subscribe("room:demo")
    for event in sub: ...
"""
import json
import os
import queue
import threading
import time
import uuid
from collections import defaultdict
from typing import Optional

from .logging_config import get_logger

log = get_logger("web.pubsub")

_MAX_HISTORY = 50


class _MemorySubscription:
    """Iterable subscription over an in-memory queue."""
    def __init__(self, backend, channel: str, sub_id: str, q: "queue.Queue"):
        self._backend = backend
        self._channel = channel
        self._sub_id = sub_id
        self._q = q

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return self._q.get(timeout=15)
        except queue.Empty:
            return {"event": "__heartbeat__", "data": {}, "ts": time.time()}

    def close(self):
        self._backend._unsubscribe(self._channel, self._sub_id)


class MemoryBackend:
    name = "memory"

    def __init__(self):
        self._subs: dict[str, dict[str, "queue.Queue"]] = defaultdict(dict)
        self._history: dict[str, list[dict]] = defaultdict(list)
        self._lock = threading.Lock()

    def publish(self, channel: str, event: str, data: dict) -> int:
        payload = {"event": event, "data": data, "ts": time.time()}
        with self._lock:
            hist = self._history[channel]
            hist.append(payload)
            if len(hist) > _MAX_HISTORY:
                del hist[:-_MAX_HISTORY]
            subs = list(self._subs.get(channel, {}).values())
        delivered = 0
        for q in subs:
            try:
                q.put_nowait(payload)
                delivered += 1
            except queue.Full:
                pass
        return delivered

    def subscribe(self, channel: str, replay: int = 0):
        sub_id = uuid.uuid4().hex
        q: "queue.Queue" = queue.Queue(maxsize=100)
        with self._lock:
            self._subs[channel][sub_id] = q
            hist = list(self._history.get(channel, []))
        # Replay recent events
        if replay > 0:
            for evt in hist[-replay:]:
                try:
                    q.put_nowait(evt)
                except queue.Full:
                    break
        return _MemorySubscription(self, channel, sub_id, q)

    def _unsubscribe(self, channel: str, sub_id: str):
        with self._lock:
            self._subs.get(channel, {}).pop(sub_id, None)

    def subscriber_count(self, channel: str) -> int:
        with self._lock:
            return len(self._subs.get(channel, {}))

    def channels(self) -> dict:
        with self._lock:
            return {ch: len(subs) for ch, subs in self._subs.items()}


class _RedisSubscription:
    def __init__(self, pubsub, channel: str):
        self._pubsub = pubsub
        self._channel = channel

    def __iter__(self):
        return self

    def __next__(self):
        msg = self._pubsub.get_message(timeout=15)
        if msg is None or msg.get("type") != "message":
            return {"event": "__heartbeat__", "data": {}, "ts": time.time()}
        try:
            payload = json.loads(msg["data"])
            return payload
        except Exception:
            return {"event": "error", "data": {}, "ts": time.time()}

    def close(self):
        try:
            self._pubsub.unsubscribe(self._channel)
        except Exception:
            pass


class RedisBackend:
    """Redis pub/sub backend.

    Subscribes on demand. Each `subscribe()` call creates a fresh
    pubsub object (a Redis pubsub channel subscription is a dedicated
    connection). Not perfectly efficient for high subscriber counts
    but fine for the small deployments this app targets.
    """
    name = "redis"

    def __init__(self, url: str):
        import redis  # noqa: F401
        self._redis_mod = redis
        self._url = url
        self._client = redis.Redis.from_url(url, decode_responses=True)

    def publish(self, channel: str, event: str, data: dict) -> int:
        payload = json.dumps({"event": event, "data": data, "ts": time.time()})
        try:
            n = self._client.publish(channel, payload)
            return int(n or 0)
        except Exception as e:
            log.warning("redis publish failed: %s", e)
            return 0

    def subscribe(self, channel: str, replay: int = 0):
        pubsub = self._client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(channel)
        return _RedisSubscription(pubsub, channel)

    def subscriber_count(self, channel: str) -> int:
        try:
            return int(self._client.pubsub_numsub(channel)[0][1] or 0)
        except Exception:
            return 0

    def channels(self) -> dict:
        try:
            chans = self._client.pubsub_channels()
            out = {}
            for ch in chans:
                info = self._client.pubsub_numsub(ch)
                out[ch] = info[0][1] if info else 0
            return out
        except Exception:
            return {}


_BACKEND = None
_BACKEND_LOCK = threading.Lock()


def get_backend():
    """Return the configured pub/sub backend (singleton)."""
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    with _BACKEND_LOCK:
        if _BACKEND is not None:
            return _BACKEND
        url = os.environ.get("REDIS_URL")
        if url:
            try:
                _BACKEND = RedisBackend(url)
                log.info("pubsub backend: redis (%s)", url)
            except ImportError:
                log.warning("REDIS_URL set but 'redis' package not installed — falling back to memory")
                _BACKEND = MemoryBackend()
            except Exception as e:
                log.warning("redis backend failed (%s) — falling back to memory", e)
                _BACKEND = MemoryBackend()
        else:
            _BACKEND = MemoryBackend()
            log.info("pubsub backend: memory")
        return _BACKEND


def reset_backend():
    """Reset the singleton (for tests)."""
    global _BACKEND
    with _BACKEND_LOCK:
        _BACKEND = None
