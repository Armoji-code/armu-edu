from flask import request, jsonify
from api import blueprint
from auth import login_required
from models import db
from models.social import Message, Group

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
    content = data.get("content", "").strip()
    if not recipient_id or not content:
        return jsonify({"error": "recipient_id and content required"}), 400
    msg = Message(sender_id=user.id, recipient_id=recipient_id, content=content)
    db.session.add(msg)
    db.session.commit()
    return jsonify(msg.to_dict()), 201

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
    data = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "content required"}), 400
    msg = Message(sender_id=user.id, group_id=group_id, content=content)
    db.session.add(msg)
    db.session.commit()
    return jsonify(msg.to_dict()), 201
