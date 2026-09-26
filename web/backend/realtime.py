"""Real-time collaboration via Flask-SocketIO.

Each client joins a "room" (a shared identifier). Calculations broadcast
to the room are visible to everyone else in it. Also tracks presence.
"""
from collections import defaultdict

from flask import request
from flask_socketio import SocketIO, join_room, leave_room, emit

# Global SocketIO instance (bound to the Flask app in main.py)
socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

# room_id -> { sid: username }
ROOMS: dict[str, dict[str, str]] = defaultdict(dict)




def _user_color(name: str) -> str:
    """Deterministic HSL color for a username (same logic as the client)."""
    h = 0
    for c in name:
        h = ((h << 5) - h + ord(c)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    hue = abs(h) % 360
    return f"hsl({hue} 65% 50%)"


def _room_users(room_id: str) -> list[str]:
    return sorted(set(ROOMS.get(room_id, {}).values()))


@socketio.on("join")
def on_join(data):
    room = (data or {}).get("room", "").strip()
    username = (data or {}).get("username", "guest").strip() or "guest"
    if not room:
        emit("error", {"error": "room is required"})
        return

    join_room(room)
    ROOMS[room][request.sid] = username

    emit("joined", {
        "room": room,
        "username": username,
        "users": _room_users(room),
    }, to=request.sid)

    # Notify everyone else in the room
    emit("user_joined", {
        "username": username,
        "users": _room_users(room),
    }, to=room, include_self=False)


@socketio.on("leave")
def on_leave(data):
    room = (data or {}).get("room", "").strip()
    username = ROOMS.get(room, {}).pop(request.sid, None)
    if username is not None:
        leave_room(room)
        emit("user_left", {
            "username": username,
            "users": _room_users(room),
        }, to=room)


@socketio.on("disconnect")
def on_disconnect():
    # Remove this sid from every room it's in
    for room, members in list(ROOMS.items()):
        username = members.pop(request.sid, None)
        if username is not None:
            emit("user_left", {
                "username": username,
                "users": _room_users(room),
            }, to=room)
        if not members:
            del ROOMS[room]


@socketio.on("broadcast_calc")
def on_broadcast(data):
    room = (data or {}).get("room", "").strip()
    if not room:
        emit("error", {"error": "room is required"})
        return

    payload = {
        "username": (data or {}).get("username", "guest"),
        "expression": (data or {}).get("expression", ""),
        "result": (data or {}).get("result", ""),
        "operation": (data or {}).get("operation"),
    }
    # Send to everyone in the room EXCEPT the sender
    emit("calc_received", payload, to=room, include_self=False)


@socketio.on("ping_presence")
def on_ping(data):
    room = (data or {}).get("room", "").strip()
    if room:
        emit("presence", {"users": _room_users(room)}, to=request.sid)




# ---------------------------------------------------------------------
# Chat events (Phase 9)
# ---------------------------------------------------------------------
@socketio.on("chat_send")
def on_chat_send(data):
    """Broadcast a chat message to everyone in the room.

    The server does NOT persist here — persistence happens via POST
    /api/chat/<room>, so clients control whether messages are stored.
    This keeps E2E flow clean: ciphertext is broadcast verbatim.
    """
    room = (data or {}).get("room", "").strip()
    if not room:
        emit("error", {"error": "room is required"})
        return

    payload = {
        "username": (data or {}).get("username", "guest"),
        "body": (data or {}).get("body", ""),
        "encrypted": bool((data or {}).get("encrypted")),
        "id": (data or {}).get("id"),
    }
    emit("chat_message", payload, to=room, include_self=False)


@socketio.on("typing_start")
def on_typing_start(data):
    room = (data or {}).get("room", "").strip()
    if not room:
        return
    emit("typing", {
        "username": (data or {}).get("username", "guest"),
        "state": "start",
    }, to=room, include_self=False)


@socketio.on("typing_stop")
def on_typing_stop(data):
    room = (data or {}).get("room", "").strip()
    if not room:
        return
    emit("typing", {
        "username": (data or {}).get("username", "guest"),
        "state": "stop",
    }, to=room, include_self=False)




# ---------------------------------------------------------------------
# WebRTC signaling (Phase 14)
#
# The server never touches media. It only relays SDP offers/answers
# and ICE candidates between peers. Peers discover each other via
# `webrtc_join` / `webrtc_leave`.
# ---------------------------------------------------------------------
# sid -> {room, username}
WEBRTC_PEERS: dict[str, dict] = {}


@socketio.on("webrtc_join")
def on_webrtc_join(data):
    room = (data or {}).get("room", "").strip()
    username = (data or {}).get("username", "guest").strip() or "guest"
    if not room:
        emit("webrtc_error", {"error": "room is required"})
        return

    # Send the joiner the list of existing peers in this room
    peers = [
        {"sid": sid, "username": info["username"]}
        for sid, info in WEBRTC_PEERS.items()
        if info["room"] == room and sid != request.sid
    ]
    WEBRTC_PEERS[request.sid] = {"room": room, "username": username}
    emit("webrtc_peer_list", {"peers": peers}, to=request.sid)

    # Notify existing peers that a new one arrived
    emit("webrtc_peer_joined",
         {"sid": request.sid, "username": username},
         to=room, include_self=False)


@socketio.on("webrtc_leave")
def on_webrtc_leave(data):
    info = WEBRTC_PEERS.pop(request.sid, None)
    if not info:
        return
    room = info["room"]
    emit("webrtc_peer_left",
         {"sid": request.sid, "username": info["username"]},
         to=room, include_self=False)


@socketio.on("webrtc_offer")
def on_webrtc_offer(data):
    target = (data or {}).get("target_sid")
    if not target:
        emit("webrtc_error", {"error": "target_sid required"})
        return
    info = WEBRTC_PEERS.get(request.sid, {})
    emit("webrtc_offer", {
        "from_sid": request.sid,
        "from_username": info.get("username", "guest"),
        "sdp": (data or {}).get("sdp"),
    }, to=target)


@socketio.on("webrtc_answer")
def on_webrtc_answer(data):
    target = (data or {}).get("target_sid")
    if not target:
        return
    info = WEBRTC_PEERS.get(request.sid, {})
    emit("webrtc_answer", {
        "from_sid": request.sid,
        "from_username": info.get("username", "guest"),
        "sdp": (data or {}).get("sdp"),
    }, to=target)


@socketio.on("webrtc_ice")
def on_webrtc_ice(data):
    target = (data or {}).get("target_sid")
    if not target:
        return
    emit("webrtc_ice", {
        "from_sid": request.sid,
        "candidate": (data or {}).get("candidate"),
    }, to=target)




# ---------------------------------------------------------------------
# DM typing + read receipts (Phase 37)
# ---------------------------------------------------------------------
@socketio.on("dm_typing_start")
def on_dm_typing_start(data):
    thread_id = (data or {}).get("thread_id")
    recipient_id = (data or {}).get("recipient_id")
    username = (data or {}).get("username", "guest")
    if not thread_id or not recipient_id:
        return
    emit("dm_typing", {
        "thread_id": thread_id,
        "username": username,
        "state": "start",
    }, to=f"user_{recipient_id}")


@socketio.on("dm_typing_stop")
def on_dm_typing_stop(data):
    thread_id = (data or {}).get("thread_id")
    recipient_id = (data or {}).get("recipient_id")
    username = (data or {}).get("username", "guest")
    if not thread_id or not recipient_id:
        return
    emit("dm_typing", {
        "thread_id": thread_id,
        "username": username,
        "state": "stop",
    }, to=f"user_{recipient_id}")


@socketio.on("dm_join")
def on_dm_join(data):
    user_id = (data or {}).get("user_id")
    if not user_id:
        return
    join_room(f"user_{user_id}")
    emit("dm_subscribed", {"user_id": user_id}, to=request.sid)


@socketio.on("dm_read")
def on_dm_read(data):
    thread_id = (data or {}).get("thread_id")
    sender_id = (data or {}).get("sender_id")
    reader_username = (data or {}).get("reader_username", "guest")
    if not thread_id or not sender_id:
        return
    emit("dm_read", {
        "thread_id": thread_id,
        "reader_username": reader_username,
    }, to=f"user_{sender_id}")


def reset_state():
    """Clear all room state (used in tests)."""
    ROOMS.clear()
    WEBRTC_PEERS.clear()
