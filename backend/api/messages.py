import os
import uuid
from datetime import datetime, timezone
from flask import request, jsonify, current_app
from werkzeug.utils import secure_filename
from api import blueprint, err, ok
from auth import login_required
from models import db
from models.social import Message, Group, MessageReaction, FlaggedMessage
from ai.moderation import scan_async
from app import socketio

_ALLOWED_EXT = {
    'jpg', 'jpeg', 'png', 'gif', 'webp',
    'pdf', 'txt', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip',
}
_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'messages')


@blueprint.route("/messages/upload", methods=["POST"])
@login_required()
def upload_message_file(user):
    if 'file' not in request.files:
        return err("no file", 400)
    f = request.files['file']
    if not f.filename:
        return err("no file", 400)
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext not in _ALLOWED_EXT:
        return jsonify({"error": f"file type .{ext} not allowed"}), 400
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    save_name = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(_UPLOAD_DIR, save_name))
    return jsonify({
        "url":  f"/static/uploads/messages/{save_name}",
        "name": secure_filename(f.filename) or save_name,
    }), 201


@blueprint.route("/messages/personal", methods=["GET"])
@login_required()
def list_personal(user):
    messages = (
        Message.query
        .filter(
            Message.group_id == None,
            (Message.sender_id == user.id) | (Message.recipient_id == user.id),
            Message.is_deleted != True,
        )
        .order_by(Message.created_at.desc())
        .all()
    )
    return jsonify([m.to_dict() for m in messages])


@blueprint.route("/messages/personal", methods=["POST"])
@login_required()
def send_personal(user):
    from models.user import User as _User
    data = request.get_json(silent=True) or {}
    recipient_id = data.get("recipient_id")
    content      = data.get("content", "").strip()
    reply_to_id  = data.get("reply_to_id")
    file_url     = data.get("file_url", "").strip()
    file_name    = data.get("file_name", "").strip()
    if not recipient_id or (not content and not file_url):
        return err("recipient_id and content or file required", 400)
    recipient = _User.query.filter_by(id=recipient_id, school_id=user.school_id).first()
    if not recipient:
        return err("recipient not found", 404)
    msg = Message(
        sender_id=user.id,
        recipient_id=recipient_id,
        content=content,
        reply_to_id=reply_to_id or None,
        file_url=file_url or None,
        file_name=file_name or None,
    )
    db.session.add(msg)
    db.session.commit()
    scan_async(msg.id, current_app._get_current_object())
    socketio.emit("message:new", msg.to_dict(), to=f"user_{recipient_id}")
    return jsonify(msg.to_dict()), 201


@blueprint.route("/messages/personal/read", methods=["POST"])
@login_required()
def mark_personal_read(user):
    data = request.get_json(silent=True) or {}
    other_id = data.get("other_id")
    if not other_id:
        return err("other_id required", 400)
    try:
        other_id = int(other_id)
    except (TypeError, ValueError):
        return err("invalid other_id", 400)
    Message.query.filter(
        Message.sender_id == other_id,
        Message.recipient_id == user.id,
        Message.is_read == False,
        Message.is_deleted != True,
    ).update({"is_read": True})
    db.session.commit()
    return ok()


@blueprint.route("/messages/personal/<int:msg_id>", methods=["PATCH"])
@login_required()
def edit_personal(user, msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.sender_id != user.id:
        return err("forbidden", 403)
    if msg.is_deleted:
        return err("cannot edit deleted message", 400)
    data = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    if not content:
        return err("content required", 400)
    msg.content   = content
    msg.edited_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(msg.to_dict())


@blueprint.route("/messages/personal/<int:msg_id>", methods=["DELETE"])
@login_required()
def delete_personal(user, msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.sender_id != user.id:
        return err("forbidden", 403)
    msg.is_deleted = True
    msg.content    = ""
    db.session.commit()
    return jsonify({"ok": True, "id": msg_id})


def _can_access_message(user, msg):
    """Check the user is a participant in the message's conversation."""
    if msg.group_id:
        group = Group.query.get(msg.group_id)
        return group is not None and user in group.members
    return msg.sender_id == user.id or msg.recipient_id == user.id


@blueprint.route("/messages/<int:msg_id>/react", methods=["POST"])
@login_required()
def react_message(user, msg_id):
    msg   = Message.query.get_or_404(msg_id)
    if not _can_access_message(user, msg):
        return err("forbidden", 403)
    data  = request.get_json(silent=True) or {}
    emoji = str(data.get("emoji", "")).strip()[:10]
    if not emoji:
        return err("emoji required", 400)
    existing = MessageReaction.query.filter_by(
        message_id=msg_id, user_id=user.id, emoji=emoji
    ).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(MessageReaction(message_id=msg_id, user_id=user.id, emoji=emoji))
    db.session.commit()
    db.session.refresh(msg)
    return jsonify(msg.to_dict())


@blueprint.route("/messages/<int:msg_id>/report", methods=["POST"])
@login_required()
def report_message(user, msg_id):
    msg = Message.query.get_or_404(msg_id)
    if not _can_access_message(user, msg):
        return err("forbidden", 403)
    if msg.sender_id == user.id:
        return err("cannot report own message", 400)
    existing = FlaggedMessage.query.filter_by(message_id=msg_id, status="pending").first()
    if not existing:
        flag = FlaggedMessage(
            message_id=msg_id,
            severity=0.6,
            reason=f"Manually reported by {user.name}",
            status="pending",
        )
        db.session.add(flag)
        db.session.commit()
    return ok()


@blueprint.route("/messages/groups/<int:group_id>", methods=["GET"])
@login_required()
def list_group_messages(user, group_id):
    group = Group.query.get_or_404(group_id)
    if user not in group.members:
        return err("forbidden", 403)
    messages = (
        Message.query
        .filter_by(group_id=group_id)
        .filter(Message.is_deleted != True)
        .order_by(Message.created_at)
        .all()
    )
    return jsonify([m.to_dict() for m in messages])


@blueprint.route("/messages/groups/<int:group_id>", methods=["POST"])
@login_required()
def send_group_message(user, group_id):
    group = Group.query.get_or_404(group_id)
    if user not in group.members:
        return err("forbidden", 403)
    data    = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    if not content:
        return err("content required", 400)
    msg = Message(sender_id=user.id, group_id=group_id, content=content)
    db.session.add(msg)
    db.session.commit()
    scan_async(msg.id, current_app._get_current_object())
    payload = {"group_id": group_id, "message": msg.to_dict()}
    for member in group.members:
        if member.id != user.id:
            socketio.emit("group_message:new", payload, to=f"user_{member.id}")
    return jsonify(msg.to_dict()), 201
