from flask import jsonify
from api import blueprint, err, ok
from auth import login_required
from models.academic import Grade

@blueprint.route("/grades", methods=["GET"])
@login_required()
def list_grades(user):
    grades = (
        Grade.query
        .filter_by(student_id=user.id)
        .order_by(Grade.created_at.desc())
        .all()
    )
    return jsonify([g.to_dict() for g in grades])
