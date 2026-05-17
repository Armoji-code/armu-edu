from app import socketio
from flask import session
from flask_socketio import join_room, emit

# In-memory board state per room: room_id -> list of stroke dicts
_board_states = {}

@socketio.on("connect")
def on_connect():
    pass

@socketio.on("disconnect")
def on_disconnect():
    pass

@socketio.on("user_join")
def on_user_join(data):
    """Client sends their user_id so we can push notifications to them."""
    uid = data.get("user_id")
    if uid:
        join_room(f"user_{uid}")

@socketio.on("wb_join")
def on_wb_join(data):
    room = data.get("room", "global")
    join_room(room)
    emit("wb_sync", {"strokes": _board_states.get(room, [])})

@socketio.on("wb_stroke")
def on_wb_stroke(data):
    room = data.get("room", "global")
    stroke = data.get("stroke")
    if stroke:
        _board_states.setdefault(room, []).append(stroke)
        emit("wb_stroke", {"stroke": stroke}, to=room, include_self=False)

@socketio.on("wb_clear")
def on_wb_clear(data):
    room = data.get("room", "global")
    _board_states[room] = []
    emit("wb_cleared", {}, to=room)
