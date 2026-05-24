from flask import request, jsonify, session
from api import blueprint, err, ok
from auth import login_required
from models import db
from models.user import User, PasswordResetToken
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
        return err("email and password required", 400)

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return err("invalid credentials", 401)

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
        return err("not authenticated", 401)
    user = User.query.get(user_id)
    if not user:
        session.clear()
        return err("not authenticated", 401)
    return jsonify(user.to_dict())

@blueprint.route("/auth/me", methods=["PATCH"])
@login_required()
def update_me(user):
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return err("name required", 400)
    user.name = name
    db.session.commit()
    return jsonify(user.to_dict())

@blueprint.route("/auth/password", methods=["POST"])
@login_required()
def change_password(user):
    if not user.can_change_password:
        return err("Password changes are disabled for this account.", 403)
    data = request.get_json(silent=True) or {}
    current = data.get("current", "")
    new_pw = data.get("new", "")
    if not user.check_password(current):
        return err("Current password is incorrect", 400)
    if len(new_pw) < 8:
        return err("New password must be at least 8 characters", 400)
    user.set_password(new_pw)
    db.session.commit()
    return ok()

@blueprint.route("/user/appearance", methods=["GET"])
@login_required()
def get_user_appearance(user):
    return jsonify((user.preferences or {}).get("appearance", {}))

@blueprint.route("/user/appearance", methods=["PATCH"])
@login_required()
def save_user_appearance(user):
    data = request.get_json(silent=True) or {}
    prefs = dict(user.preferences or {})

    allowed_colors = ("g1","g2","g3","dark_text2","dark_text3","light_text2","light_text3")
    colors = {}
    if isinstance(data.get("colors"), dict):
        colors = {k: v for k, v in data["colors"].items()
                  if k in allowed_colors and isinstance(v, str) and v.startswith('#') and len(v) in (4,7)}

    allowed_families = {
        'DM Sans','Inter','Roboto','Roboto Condensed','Noto Sans','Nunito','Poppins',
        'Space Grotesk','Plus Jakarta Sans','Lato',
        'Arial','Georgia','Times New Roman','Trebuchet MS','Verdana',
    }
    font = {}
    if isinstance(data.get("font"), dict):
        fd = data["font"]
        if fd.get("family") in allowed_families:
            font["family"] = fd["family"]
        if isinstance(fd.get("size"), (int, float)):
            font["size"] = max(11, min(20, int(fd["size"])))
        if isinstance(fd.get("weight"), (int, float)) and int(fd["weight"]) in (300,400,500,600,700):
            font["weight"] = int(fd["weight"])

    prefs["appearance"] = {"colors": colors, "font": font}
    user.preferences = prefs
    db.session.commit()
    return ok()


@blueprint.route("/auth/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return err("email required", 400)

    user = User.query.filter_by(email=email).first()
    if not user:
        return ok()  # don't reveal whether email exists

    # Invalidate and purge prior tokens for this user
    PasswordResetToken.query.filter_by(user_id=user.id).delete()
    db.session.flush()

    token_obj, code = PasswordResetToken.generate(user.id)
    db.session.add(token_obj)
    db.session.commit()

    try:
        from mailer import send_reset_email
        send_reset_email(user.email, code, user.name)
    except ValueError as exc:
        return err(str(exc), 500)
    except Exception:
        from flask import current_app
        current_app.logger.exception("Failed to send password reset email to %s", user.email)
        return err("Failed to send reset email — contact your administrator.", 500)

    return ok()


@blueprint.route("/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}
    email  = data.get("email", "").strip().lower()
    code   = data.get("code", "").strip()
    new_pw = data.get("new_password", "")

    if not email or not code or not new_pw:
        return err("email, code, and new_password required", 400)
    if len(new_pw) < 8:
        return err("Password must be at least 8 characters", 400)

    user = User.query.filter_by(email=email).first()
    if not user:
        return err("Invalid code", 400)

    token_obj = PasswordResetToken.verify(user.id, code)
    if not token_obj:
        return err("Invalid or expired code", 400)

    token_obj.used = True
    user.set_password(new_pw)
    db.session.commit()
    return ok()
