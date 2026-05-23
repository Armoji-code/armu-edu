from datetime import datetime, timezone
from flask import request, jsonify, current_app
from api import blueprint
from auth import login_required
from models import db
from models.social import Message, Group, MessageReaction, FlaggedMessage
from ai.moderation import scan_async


@blueprint.route("/messages/personal", methods=["GET"])
@login_required()
def list_personal(user):
    messages = (
        Message.query
        .filter(
            Message.group_id == None,
            (Message.sender_id == user.id) | (Message.recipient_id == user.id),
        )
        .order_by(Message.created_at.desc())
        .all()
    )
    return jsonify([m.to_dict() for m in messages])


@blueprint.route("/messages/personal", methods=["POST"])
@login_required()
def send_personal(user):
    data = request.get_json(silent=True) or {}
    recipient_id = data.get("recipient_id")
    content      = data.get("content", "").strip()
    reply_to_id  = data.get("reply_to_id")
    if not recipient_id or not content:
        return jsonify({"error": "recipient_id and content required"}), 400
    msg = Message(
        sender_id=user.id,
        recipient_id=recipient_id,
        content=content,
        reply_to_id=reply_to_id or None,
    )
    db.session.add(msg)
    db.session.commit()
    scan_async(msg.id, current_app._get_current_object())
    return jsonify(msg.to_dict()), 201


@blueprint.route("/messages/personal/<int:msg_id>", methods=["PATCH"])
@login_required()
def edit_personal(user, msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.sender_id != user.id:
        return jsonify({"error": "forbidden"}), 403
    if msg.is_deleted:
        return jsonify({"error": "cannot edit deleted message"}), 400
    data = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "content required"}), 400
    msg.content   = content
    msg.edited_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(msg.to_dict())


@blueprint.route("/messages/personal/<int:msg_id>", methods=["DELETE"])
@login_required()
def delete_personal(user, msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.sender_id != user.id:
        return jsonify({"error": "forbidden"}), 403
    msg.is_deleted = True
    msg.content    = ""
    db.session.commit()
    return jsonify({"ok": True, "id": msg_id})


@blueprint.route("/messages/<int:msg_id>/react", methods=["POST"])
@login_required()
def react_message(user, msg_id):
    msg   = Message.query.get_or_404(msg_id)
    data  = request.get_json(silent=True) or {}
    emoji = str(data.get("emoji", "")).strip()[:10]
    if not emoji:
        return jsonify({"error": "emoji required"}), 400
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
    if msg.sender_id == user.id:
        return jsonify({"error": "cannot report own message"}), 400
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
    return jsonify({"ok": True})


@blueprint.route("/messages/groups/<int:group_id>", methods=["GET"])
@login_required()
def list_group_messages(user, group_id):
    group = Group.query.get_or_404(group_id)
    if user not in group.members:
        return jsonify({"error": "forbidden"}), 403
    messages = (
        Message.query
        .filter_by(group_id=group_id)
        .order_by(Message.created_at)
        .all()
    )
    return jsonify([m.to_dict() for m in messages])


@blueprint.route("/messages/groups/<int:group_id>", methods=["POST"])
@login_required()
def send_group_message(user, group_id):
    group = Group.query.get_or_404(group_id)
    if user not in group.members:
        return jsonify({"error": "forbidden"}), 403
    data    = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "content required"}), 400
    msg = Message(sender_id=user.id, group_id=group_id, content=content)
    db.session.add(msg)
    db.session.commit()
    scan_async(msg.id, current_app._get_current_object())
    return jsonify(msg.to_dict()), 201
