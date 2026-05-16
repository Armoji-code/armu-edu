from flask import request, jsonify, session
from api import blueprint
from models import db
from models.user import User

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

    session["user_id"] = user.id
    session.permanent = True
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
