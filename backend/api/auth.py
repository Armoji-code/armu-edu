from flask import request, jsonify, session
from api import blueprint
from auth import login_required
from models import db
from models.user import User
from models.school import School

@blueprint.route("/branding", methods=["GET"])
def get_branding():
    school = School.query.first()
    if not school:
        return jsonify({})
    return jsonify((school.settings or {}).get("branding", {}))


@blueprint.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "email and password required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "invalid credentials"}), 401

    session["user_id"]   = user.id
    session["user_name"] = user.name
    session.permanent    = True
    return jsonify(user.to_dict())

@blueprint.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "logged out"})

@blueprint.route("/auth/me", methods=["GET"])
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not authenticated"}), 401
    user = User.query.get(user_id)
    if not user:
        session.clear()
        return jsonify({"error": "not authenticated"}), 401
    return jsonify(user.to_dict())

@blueprint.route("/auth/me", methods=["PATCH"])
@login_required()
def update_me(user):
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    user.name = name
    db.session.commit()
    return jsonify(user.to_dict())

@blueprint.route("/auth/password", methods=["POST"])
@login_required()
def change_password(user):
    if not user.can_change_password:
        return jsonify({"error": "Password changes are disabled for this account."}), 403
    data = request.get_json(silent=True) or {}
    current = data.get("current", "")
    new_pw = data.get("new", "")
    if not user.check_password(current):
        return jsonify({"error": "Current password is incorrect"}), 400
    if len(new_pw) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400
    user.set_password(new_pw)
    db.session.commit()
    return jsonify({"ok": True})

@blueprint.route("/user/appearance", methods=["GET"])
@login_required()
def get_user_appearance(user):
    return jsonify((user.preferences or {}).get("appearance", {}))

@blueprint.route("/user/appearance", methods=["PATCH"])
@login_required()
def save_user_appearance(user):
    data = request.get_json(silent=True) or {}
    prefs = dict(user.preferences or {})
    allowed = ("g1","g2","g3","dark_text2","dark_text3","light_text2","light_text3")
    colors = {}
    if isinstance(data.get("colors"), dict):
        colors = {k: v for k, v in data["colors"].items() if k in allowed and isinstance(v, str) and v.startswith('#') and len(v) in (4,7)}
    prefs["appearance"] = {"colors": colors}
    user.preferences = prefs
    db.session.commit()
    return jsonify({"ok": True})
