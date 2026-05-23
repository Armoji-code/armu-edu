from flask import request, jsonify
from datetime import datetime, timezone
from api import blueprint, err, ok
from auth import login_required
from models.academic import Assignment, Grade
from models import db

@blueprint.route("/homework", methods=["GET"])
@login_required()
def list_homework(user):
    if not user.klass:
        return jsonify([])

    subject_ids = [s.id for s in user.klass.subjects]
    assignments = (
        Assignment.query
        .filter(Assignment.subject_id.in_(subject_ids), Assignment.type == "homework")
        .order_by(Assignment.due_date)
        .all()
    )

    completed_ids = {
        g.assignment_id for g in Grade.query.filter_by(student_id=user.id).all()
    }

    result = []
    for a in assignments:
        d = a.to_dict()
        d["completed"] = a.id in completed_ids
        result.append(d)

    return jsonify(result)
