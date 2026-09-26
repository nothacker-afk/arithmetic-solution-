"""Real-time collaboration + chat + WebRTC + DM signaling."""
from collections import defaultdict

from flask import request
from flask_socketio import SocketIO, join_room, leave_room, emit

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

ROOMS = defaultdict(dict)
WEBRTC_PEERS = {}


def _room_users(room_id):
    return sorted(set(ROOMS.get(room_id, {}).values()))


def _user_color(name):
    h = 0
    for c in name:
        h = ((h << 5) - h + ord(c)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return f"hsl({abs(h) % 360} 65% 50%)"


# ---------------------------------------------------------------------
# Room collaboration
# ---------------------------------------------------------------------
@socketio.on("join")
def on_join(data):
    room = (data or {}).get("room", "").strip()
    username = (data or {}).get("username", "guest").strip() or "guest"
    if not room:
        emit("error", {"error": "room is required"})
        return
    join_room(room)
    ROOMS[room][request.sid] = username
    emit("joined", {"room": room, "username": username,
                    "color": _user_color(username),
                    "users": _room_users(room)}, to=request.sid)
    emit("user_joined", {"username": username, "color": _user_color(username),
                         "users": _room_users(room)},
         to=room, include_self=False)


@socketio.on("leave")
def on_leave(data):
    room = (data or {}).get("room", "").strip()
    username = ROOMS.get(room, {}).pop(request.sid, None)
    if username is not None:
        leave_room(room)
        emit("user_left", {"username": username,
                           "users": _room_users(room)}, to=room)


@socketio.on("disconnect")
def on_disconnect():
    WEBRTC_PEERS.pop(request.sid, None)
    for room, members in list(ROOMS.items()):
        username = members.pop(request.sid, None)
        if username is not None:
            emit("user_left", {"username": username,
                               "users": _room_users(room)}, to=room)
        if not members:
            del ROOMS[room]


@socketio.on("broadcast_calc")
def on_broadcast(data):
    room = (data or {}).get("room", "").strip()
    if not room:
        return
    emit("calc_received", {
        "username": (data or {}).get("username", "guest"),
        "expression": (data or {}).get("expression", ""),
        "result": (data or {}).get("result", ""),
    }, to=room, include_self=False)


# ---------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------
@socketio.on("chat_send")
def on_chat_send(data):
    room = (data or {}).get("room", "").strip()
    if not room:
        return
    emit("chat_message", {
        "username": (data or {}).get("username", "guest"),
        "body": (data or {}).get("body", ""),
        "encrypted": bool((data or {}).get("encrypted")),
        "id": (data or {}).get("id"),
    }, to=room, include_self=False)


@socketio.on("typing_start")
def on_typing_start(data):
    room = (data or {}).get("room", "").strip()
    if room:
        emit("typing", {"username": (data or {}).get("username", "guest"),
                        "state": "start"}, to=room, include_self=False)


@socketio.on("typing_stop")
def on_typing_stop(data):
    room = (data or {}).get("room", "").strip()
    if room:
        emit("typing", {"username": (data or {}).get("username", "guest"),
                        "state": "stop"}, to=room, include_self=False)


# ---------------------------------------------------------------------
# DM typing + read receipts (Phase 37)
# ---------------------------------------------------------------------
@socketio.on("dm_join")
def on_dm_join(data):
    user_id = (data or {}).get("user_id")
    if not user_id:
        return
    join_room(f"user_{user_id}")
    emit("dm_subscribed", {"user_id": user_id}, to=request.sid)


@socketio.on("dm_typing_start")
def on_dm_typing_start(data):
    thread_id = (data or {}).get("thread_id")
    recipient_id = (data or {}).get("recipient_id")
    username = (data or {}).get("username", "guest")
    if not thread_id or not recipient_id:
        return
    emit("dm_typing", {"thread_id": thread_id, "username": username,
                       "state": "start"}, to=f"user_{recipient_id}")


@socketio.on("dm_typing_stop")
def on_dm_typing_stop(data):
    thread_id = (data or {}).get("thread_id")
    recipient_id = (data or {}).get("recipient_id")
    username = (data or {}).get("username", "guest")
    if not thread_id or not recipient_id:
        return
    emit("dm_typing", {"thread_id": thread_id, "username": username,
                       "state": "stop"}, to=f"user_{recipient_id}")


@socketio.on("dm_read")
def on_dm_read(data):
    thread_id = (data or {}).get("thread_id")
    sender_id = (data or {}).get("sender_id")
    reader_username = (data or {}).get("reader_username", "guest")
    if not thread_id or not sender_id:
        return
    emit("dm_read", {"thread_id": thread_id,
                     "reader_username": reader_username}, to=f"user_{sender_id}")


# ---------------------------------------------------------------------
# WebRTC
# ---------------------------------------------------------------------
@socketio.on("webrtc_join")
def on_webrtc_join(data):
    room = (data or {}).get("room", "").strip()
    username = (data or {}).get("username", "guest").strip() or "guest"
    if not room:
        return
    peers = [{"sid": sid, "username": info["username"]}
             for sid, info in WEBRTC_PEERS.items()
             if info["room"] == room and sid != request.sid]
    WEBRTC_PEERS[request.sid] = {"room": room, "username": username}
    emit("webrtc_peer_list", {"peers": peers}, to=request.sid)
    emit("webrtc_peer_joined", {"sid": request.sid, "username": username},
         to=room, include_self=False)


@socketio.on("webrtc_leave")
def on_webrtc_leave(data):
    info = WEBRTC_PEERS.pop(request.sid, None)
    if info:
        emit("webrtc_peer_left", {"sid": request.sid, "username": info["username"]},
             to=info["room"], include_self=False)


@socketio.on("webrtc_offer")
def on_webrtc_offer(data):
    target = (data or {}).get("target_sid")
    if not target:
        return
    info = WEBRTC_PEERS.get(request.sid, {})
    emit("webrtc_offer", {"from_sid": request.sid,
                          "from_username": info.get("username", "guest"),
                          "sdp": (data or {}).get("sdp")}, to=target)


@socketio.on("webrtc_answer")
def on_webrtc_answer(data):
    target = (data or {}).get("target_sid")
    if not target:
        return
    info = WEBRTC_PEERS.get(request.sid, {})
    emit("webrtc_answer", {"from_sid": request.sid,
                           "from_username": info.get("username", "guest"),
                           "sdp": (data or {}).get("sdp")}, to=target)


@socketio.on("webrtc_ice")
def on_webrtc_ice(data):
    target = (data or {}).get("target_sid")
    if not target:
        return
    emit("webrtc_ice", {"from_sid": request.sid,
                        "candidate": (data or {}).get("candidate")}, to=target)




# ---------------------------------------------------------------------
# Screen sharing (Phase 48)
# ---------------------------------------------------------------------
@socketio.on("screen_share_start")
def on_screen_share_start(data):
    """Announce to the room that this user is sharing their screen.

    Actual media flows peer-to-peer via WebRTC — this is only a
    signaling/broadcast event so peers know to expect a new video track.
    """
    room = (data or {}).get("room", "").strip()
    username = (data or {}).get("username", "guest")
    if not room:
        return
    emit("screen_share_started", {
        "sid": request.sid,
        "username": username,
    }, to=room, include_self=False)


@socketio.on("screen_share_stop")
def on_screen_share_stop(data):
    room = (data or {}).get("room", "").strip()
    username = (data or {}).get("username", "guest")
    if not room:
        return
    emit("screen_share_stopped", {
        "sid": request.sid,
        "username": username,
    }, to=room, include_self=False)


@socketio.on("screen_track_ready")
def on_screen_track_ready(data):
    """Notify one specific peer that a new track is about to arrive."""
    target = (data or {}).get("target_sid")
    if not target:
        return
    emit("screen_track_ready", {
        "from_sid": request.sid,
    }, to=target)


def reset_state():
    ROOMS.clear()
    WEBRTC_PEERS.clear()
