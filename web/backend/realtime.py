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


def reset_state():
    """Clear all room state (used in tests)."""
    ROOMS.clear()
