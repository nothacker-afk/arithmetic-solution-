"""GraphQL subscriptions (Phase 77).

Adds a Strawberry subscription schema alongside the existing query +
mutation schema. Uses an in-process asyncio queue backed by the pubsub
abstraction (Phase 69), so it works with either the memory or Redis
backend.

Usage from the client (via graphql-ws over WebSocket):

    subscription {
      messageAdded(room: "demo") { id sender body encrypted }
      userStatusChanged { username state emoji message }
      dmReceived { id sender body encrypted }
    }

Mounting: the runner extends the existing /graphql view to also
accept the `graphql-transport-ws` subprotocol when a WebSocket-capable
server is available. On Termux with werkzeug/threading, this endpoint
is available via a separate polling fallback at /api/graphql/poll.

Endpoints:
    POST /api/graphql/emit           {channel, event, data}  (auth required)
    GET  /api/graphql/subscribe?channel=...&limit=N&timeout=S
         — long-poll fallback (returns up to `limit` events within `timeout`)
"""
import json
import queue
import time
from typing import AsyncGenerator, Optional

import strawberry
from flask import Blueprint, request, jsonify, g

from .auth import require_auth
from .rate_limit import rate_limit
from .pubsub import get_backend

gql_sub_bp = Blueprint("graphql_sub", __name__, url_prefix="/api/graphql")


# ---------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------
@gql_sub_bp.route("/emit", methods=["POST"])
@require_auth
@rate_limit(max_calls=60, window_seconds=60)
def emit():
    """Manually publish an event to a channel. Used by tests + tooling."""
    data = request.get_json(silent=True) or {}
    channel = (data.get("channel") or "").strip()
    event = (data.get("event") or "message").strip()
    payload = data.get("data") or {}
    if not channel:
        return jsonify({"error": "channel required"}), 400
    n = get_backend().publish(channel, event, payload)
    return jsonify({"delivered": n, "channel": channel, "event": event})


@gql_sub_bp.route("/subscribe", methods=["GET"])
@require_auth
def subscribe_long_poll():
    """Long-poll fallback for GraphQL subscribers.

    Query params:
        channel  — subscription channel (required)
        event    — optional event name filter
        limit    — max events to return (default 10, max 100)
        timeout  — seconds to wait for the first event (default 25, max 60)
    """
    channel = (request.args.get("channel") or "").strip()
    if not channel:
        return jsonify({"error": "channel required"}), 400
    event_filter = (request.args.get("event") or "").strip() or None
    try:
        limit = min(int(request.args.get("limit", 10)), 100)
    except ValueError:
        limit = 10
    try:
        timeout = min(int(request.args.get("timeout", 25)), 60)
    except ValueError:
        timeout = 25

    backend = get_backend()
    sub = backend.subscribe(channel)
    events = []
    start = time.time()
    try:
        while len(events) < limit and time.time() - start < timeout:
            try:
                evt = next(iter(sub))
            except StopIteration:
                break
            if evt.get("event") == "__heartbeat__":
                continue
            if event_filter and evt.get("event") != event_filter:
                continue
            events.append({
                "event": evt.get("event"),
                "data": evt.get("data"),
                "ts": evt.get("ts"),
            })
            # Return early if we have at least one and there's more waiting
            if events and time.time() - start > 1:
                break
    finally:
        try:
            sub.close()
        except Exception:
            pass

    return jsonify({
        "channel": channel,
        "event_filter": event_filter,
        "count": len(events),
        "events": events,
    })


# ---------------------------------------------------------------------
# Strawberry subscription schema
# ---------------------------------------------------------------------
try:
    import asyncio
    from typing import List
    import strawberry

    @strawberry.type
    class SubMessage:
        id: int
        sender: str
        body: str
        encrypted: bool
        room: Optional[str] = None

    @strawberry.type
    class SubStatus:
        username: str
        state: str
        emoji: Optional[str] = None
        message: Optional[str] = None

    @strawberry.type
    class Subscription:
        @strawberry.subscription
        async def message_added(self, room: str) -> AsyncGenerator[SubMessage, None]:
            """Streams chat messages for a room via the pubsub backend."""
            backend = get_backend()
            sub = backend.subscribe(f"room:{room}")
            try:
                while True:
                    try:
                        evt = next(iter(sub))
                    except StopIteration:
                        await asyncio.sleep(0.5)
                        continue
                    if evt.get("event") == "__heartbeat__":
                        await asyncio.sleep(0.1)
                        continue
                    if evt.get("event") != "chat_message":
                        continue
                    d = evt.get("data") or {}
                    yield SubMessage(
                        id=int(d.get("id", 0)),
                        sender=str(d.get("username", "?")),
                        body=str(d.get("body", "")),
                        encrypted=bool(d.get("encrypted")),
                        room=room,
                    )
            finally:
                try:
                    sub.close()
                except Exception:
                    pass

        @strawberry.subscription
        async def user_status_changed(self) -> AsyncGenerator[SubStatus, None]:
            backend = get_backend()
            sub = backend.subscribe("status:global")
            try:
                while True:
                    try:
                        evt = next(iter(sub))
                    except StopIteration:
                        await asyncio.sleep(0.5)
                        continue
                    if evt.get("event") == "__heartbeat__":
                        continue
                    if evt.get("event") != "user_status":
                        continue
                    d = evt.get("data") or {}
                    yield SubStatus(
                        username=str(d.get("username", "?")),
                        state=str(d.get("state", "available")),
                        emoji=d.get("emoji"),
                        message=d.get("message"),
                    )
            finally:
                try:
                    sub.close()
                except Exception:
                    pass

    @strawberry.type
    class _SubscriptionQuery:
        @strawberry.field
        def subscription_ping(self) -> str:
            return "pong"

    subscription_schema = strawberry.Schema(
        query=_SubscriptionQuery,
        subscription=Subscription,
    )
    HAS_SUBSCRIPTION_SCHEMA = True
except Exception as e:  # pragma: no cover
    import logging
    logging.getLogger("web.graphql_sub").warning(
        "subscription schema failed to build: %s", e
    )
    subscription_schema = None
    HAS_SUBSCRIPTION_SCHEMA = False
