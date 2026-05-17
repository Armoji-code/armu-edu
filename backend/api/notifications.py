from flask import jsonify, request
from api import blueprint
from auth import login_required
from models import db
from models.notification import Notification


@blueprint.route("/notifications", methods=["GET"])
@login_required()
def list_notifications(user):
    notifs = (
        Notification.query
        .filter_by(user_id=user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    unread = sum(1 for n in notifs if not n.read)
    return jsonify({"unread": unread, "notifications": [n.to_dict() for n in notifs]})


@blueprint.route("/notifications/<int:notif_id>/read", methods=["POST"])
@login_required()
def mark_read(user, notif_id):
    n = Notification.query.get_or_404(notif_id)
    if n.user_id != user.id:
        return jsonify({"error": "forbidden"}), 403
    n.read = True
    db.session.commit()
    return jsonify({"ok": True})


@blueprint.route("/notifications/read-all", methods=["POST"])
@login_required()
def mark_all_read(user):
    Notification.query.filter_by(user_id=user.id, read=False).update({"read": True})
    db.session.commit()
    return jsonify({"ok": True})
