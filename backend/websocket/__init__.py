import json
from app import socketio
from flask import session
from flask_socketio import join_room, emit

# In-memory cache per room for fast collaborative sync
_board_states = {}


def _is_persistent(room):
    """Meeting boards are ephemeral; personal and group boards are saved to DB."""
    return not room.startswith('meeting_')


def _check_room_access(room):
    uid = str(session.get('user_id', ''))
    if not uid:
        return False
    if room.startswith('personal_'):
        return uid == room[len('personal_'):]
    if room.startswith('group_'):
        return True  # secret-link model; knowing the code is the credential
    if room.startswith('meeting_'):
        from websocket.meeting import _rooms
        return uid in _rooms.get(room[len('meeting_'):], {})
    return False


def _load_room(room):
    """Load strokes from DB (persistent rooms) or in-memory (meeting rooms)."""
    if not _is_persistent(room):
        return _board_states.get(room, [])
    try:
        from models.wb import WbStroke
        rows = WbStroke.query.filter_by(room=room).all()
        strokes = [json.loads(r.data) for r in rows]
        _board_states[room] = strokes
        return strokes
    except Exception:
        return _board_states.get(room, [])


def _save_stroke(room, stroke):
    if not _is_persistent(room):
        return
    sid = stroke.get('id', '')
    if not sid:
        return
    try:
        from models import db
        from models.wb import WbStroke
        row = WbStroke.query.filter_by(room=room, stroke_id=sid).first()
        if row:
            row.data = json.dumps(stroke)
        else:
            db.session.add(WbStroke(room=room, stroke_id=sid, data=json.dumps(stroke)))
        db.session.commit()
    except Exception:
        pass


def _delete_stroke_db(room, sid):
    if not _is_persistent(room):
        return
    try:
        from models import db
        from models.wb import WbStroke
        WbStroke.query.filter_by(room=room, stroke_id=sid).delete()
        db.session.commit()
    except Exception:
        pass


def _clear_room_db(room):
    if not _is_persistent(room):
        return
    try:
        from models import db
        from models.wb import WbStroke
        WbStroke.query.filter_by(room=room).delete()
        db.session.commit()
    except Exception:
        pass


@socketio.on("connect")
def on_connect():
    pass


@socketio.on("user_join")
def on_user_join(data):
    """Join the notification room for the current session user."""
    uid = str(session.get("user_id", ""))
    if uid:
        join_room(f"user_{uid}")


@socketio.on("wb_join")
def on_wb_join(data):
    room = data.get("room", "global")
    if not _check_room_access(room):
        emit("wb_error", {"error": "unauthorized"})
        return
    join_room(room)
    emit("wb_sync", {"strokes": _load_room(room)})


@socketio.on("wb_stroke")
def on_wb_stroke(data):
    room = data.get("room", "global")
    if not _check_room_access(room):
        return
    stroke = data.get("stroke")
    if stroke:
        _board_states.setdefault(room, []).append(stroke)
        _save_stroke(room, stroke)
        emit("wb_stroke", {"stroke": stroke}, to=room, include_self=False)


@socketio.on("wb_clear")
def on_wb_clear(data):
    room = data.get("room", "global")
    if not _check_room_access(room):
        return
    _board_states[room] = []
    _clear_room_db(room)
    emit("wb_cleared", {}, to=room)


@socketio.on("wb_update_stroke")
def on_wb_update_stroke(data):
    room = data.get("room", "global")
    if not _check_room_access(room):
        return
    stroke = data.get("stroke")
    if stroke and stroke.get("id"):
        board = _board_states.get(room, [])
        for i, s in enumerate(board):
            if s.get("id") == stroke["id"]:
                board[i] = stroke
                break
        _save_stroke(room, stroke)
        emit("wb_update_stroke", {"stroke": stroke}, to=room, include_self=False)


@socketio.on("wb_delete_stroke")
def on_wb_delete_stroke(data):
    room = data.get("room", "global")
    if not _check_room_access(room):
        return
    sid = data.get("id")
    if sid:
        _board_states[room] = [s for s in _board_states.get(room, []) if s.get("id") != sid]
        _delete_stroke_db(room, sid)
        emit("wb_delete_stroke", {"id": sid}, to=room, include_self=False)
