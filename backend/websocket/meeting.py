from app import socketio
from flask import session, request
from flask_socketio import join_room, leave_room, emit
from models.user import User

# room_code -> {str(user_id): {"name": str, "sid": str}}
_rooms = {}


def _name():
    uid = session.get("user_id")
    name = session.get("user_name")
    if not name and uid:
        try:
            u = User.query.get(uid)
            name = u.name if u else "Unknown"
            session["user_name"] = name
        except Exception:
            name = "Unknown"
    return str(uid) if uid else None, name or "Unknown"


@socketio.on("meeting:join")
def on_meeting_join(data):
    room_code = data.get("room_code", "").strip()
    uid, name = _name()
    if not room_code or not uid:
        return

    join_room(f"meeting_{room_code}")
    _rooms.setdefault(room_code, {})

    existing = [
        {"id": peer_uid, "name": info["name"]}
        for peer_uid, info in _rooms[room_code].items()
        if peer_uid != uid
    ]
    emit("meeting:peers", {"peers": existing})

    emit("meeting:peer-joined", {"id": uid, "name": name},
         to=f"meeting_{room_code}", include_self=False)

    _rooms[room_code][uid] = {"name": name, "sid": request.sid}


@socketio.on("meeting:leave")
def on_meeting_leave(data):
    room_code = data.get("room_code", "").strip()
    uid, _ = _name()
    if not room_code or not uid:
        return

    leave_room(f"meeting_{room_code}")
    if room_code in _rooms:
        _rooms[room_code].pop(uid, None)
        if not _rooms[room_code]:
            del _rooms[room_code]

    emit("meeting:peer-left", {"id": uid},
         to=f"meeting_{room_code}", include_self=False)


@socketio.on("meeting:signal")
def on_meeting_signal(data):
    to_uid    = str(data.get("to", ""))
    room_code = data.get("room_code", "").strip()
    signal    = data.get("data")
    uid, _    = _name()
    if not to_uid or not room_code or not uid:
        return

    target = _rooms.get(room_code, {}).get(to_uid)
    if target:
        emit("meeting:signal", {"from": uid, "data": signal}, to=target["sid"])


@socketio.on("meeting:chat")
def on_meeting_chat(data):
    room_code = data.get("room_code", "").strip()
    text      = str(data.get("text", "")).strip()[:2000]
    uid, name = _name()
    if not room_code or not uid or not text:
        return
    if room_code not in _rooms or uid not in _rooms[room_code]:
        return
    emit("meeting:chat", {"uid": uid, "name": name, "text": text},
         to=f"meeting_{room_code}")


@socketio.on("disconnect")
def on_meeting_disconnect():
    uid, _ = _name()
    if not uid:
        return
    # Remove from any meeting rooms this socket was in
    for room_code, participants in list(_rooms.items()):
        if uid in participants and participants[uid]["sid"] == request.sid:
            participants.pop(uid, None)
            emit("meeting:peer-left", {"id": uid},
                 to=f"meeting_{room_code}", include_self=False)
            if not participants:
                del _rooms[room_code]
