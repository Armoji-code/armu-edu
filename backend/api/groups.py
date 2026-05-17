from flask import request, jsonify
from api import blueprint
from auth import login_required
from models import db
from models.social import Group, group_members
from models.user import User


@blueprint.route("/groups", methods=["GET"])
@login_required()
def list_groups(user):
    groups = [
        g for g in Group.query.all()
        if user in g.members
    ]
    return jsonify([_group_dict(g, user.id) for g in groups])


@blueprint.route("/groups", methods=["POST"])
@login_required()
def create_group(user):
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    g = Group(name=name)
    g.members.append(user)
    db.session.add(g)
    db.session.commit()
    return jsonify(_group_dict(g, user.id)), 201


@blueprint.route("/groups/<int:group_id>", methods=["GET"])
@login_required()
def get_group(user, group_id):
    g = Group.query.get_or_404(group_id)
    if user not in g.members:
        return jsonify({"error": "forbidden"}), 403
    return jsonify(_group_dict(g, user.id))


@blueprint.route("/groups/<int:group_id>/members", methods=["POST"])
@login_required()
def add_member(user, group_id):
    g = Group.query.get_or_404(group_id)
    if user not in g.members:
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "email required"}), 400
    target = User.query.filter_by(email=email, school_id=user.school_id).first()
    if not target:
        return jsonify({"error": "user not found in your school"}), 404
    if target in g.members:
        return jsonify({"error": "already a member"}), 409
    g.members.append(target)
    db.session.commit()
    return jsonify(_group_dict(g, user.id))


@blueprint.route("/groups/<int:group_id>/leave", methods=["DELETE"])
@login_required()
def leave_group(user, group_id):
    g = Group.query.get_or_404(group_id)
    if user not in g.members:
        return jsonify({"error": "not a member"}), 400
    g.members.remove(user)
    db.session.commit()
    return jsonify({"ok": True})


@blueprint.route("/users/classmates", methods=["GET"])
@login_required()
def classmates(user):
    users = User.query.filter_by(school_id=user.school_id).all()
    return jsonify([
        {"id": u.id, "name": u.name, "email": u.email}
        for u in users if u.id != user.id
    ])


def _group_dict(g, my_id):
    return {
        "id": g.id,
        "name": g.name,
        "class_id": g.class_id,
        "member_count": len(g.members),
        "members": [
            {"id": m.id, "name": m.name, "email": m.email, "is_me": m.id == my_id}
            for m in g.members
        ],
    }
