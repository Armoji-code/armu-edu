from datetime import datetime, timezone
from flask import request, jsonify, current_app
from api import blueprint, err, ok
from auth import login_required
from models import db
from models.meeting import Meeting
from models.user import User
from websocket.meeting import _rooms


@blueprint.route("/meetings/ice-config", methods=["GET"])
@login_required()
def meetings_ice_config(user):
    school = _get_school(user)
    s = school.settings or {} if school else {}

    servers = [
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": "stun:stun1.l.google.com:19302"},
    ]

    turn_url  = s.get("turn_url",        current_app.config.get("TURN_URL", ""))
    turn_user = s.get("turn_username",   current_app.config.get("TURN_USERNAME", ""))
    turn_cred = s.get("turn_credential", current_app.config.get("TURN_CREDENTIAL", ""))
    if turn_url and turn_user and turn_cred:
        servers.append({"urls": turn_url, "username": turn_user, "credential": turn_cred})

    return jsonify({"ice_servers": servers})


@blueprint.route("/meetings", methods=["GET"])
@login_required()
def list_meetings(user):
    q = Meeting.query.filter_by(is_active=True)
    if user.role == "student":
        q = q.filter(
            (Meeting.class_id == user.class_id) | (Meeting.host_id == user.id)
        )
    elif user.role == "teacher":
        from models.school import Subject
        class_ids = [s.class_id for s in Subject.query.filter_by(teacher_id=user.id).all()]
        q = q.filter(
            Meeting.class_id.in_(class_ids) | (Meeting.host_id == user.id)
        )
    meetings = q.order_by(Meeting.created_at.desc()).all()
    return jsonify([
        m.to_dict(participant_count=len(_rooms.get(m.room_code, {})))
        for m in meetings
    ])


def _teacher_class_ids(teacher_id):
    from models.school import Subject
    return {s.class_id for s in Subject.query.filter_by(teacher_id=teacher_id).all()}


@blueprint.route("/meetings", methods=["POST"])
@login_required()
def create_meeting(user):
    data     = request.get_json(silent=True) or {}
    title    = data.get("title", "").strip() or "Meeting"
    class_id = data.get("class_id") or None

    if user.role == "student" and class_id and class_id != user.class_id:
        return err("forbidden", 403)
    if user.role == "teacher" and class_id and class_id not in _teacher_class_ids(user.id):
        return err("forbidden", 403)

    m = Meeting(title=title, host_id=user.id, class_id=class_id)
    db.session.add(m)
    db.session.commit()
    return jsonify(m.to_dict()), 201


@blueprint.route("/meetings/<int:mid>", methods=["DELETE"])
@login_required()
def end_meeting(user, mid):
    m = Meeting.query.get_or_404(mid)
    if m.host_id != user.id:
        if user.role == "admin":
            pass  # admins can end any meeting
        elif user.role == "teacher" and m.class_id in _teacher_class_ids(user.id):
            pass  # teachers can force-end meetings in their own classes
        else:
            return err("forbidden", 403)
    m.is_active = False
    m.ended_at  = datetime.now(timezone.utc)
    db.session.commit()
    return ok()


def _get_school(user):
    try:
        from models.school import School
        return School.query.get(user.school_id)
    except Exception:
        return None
