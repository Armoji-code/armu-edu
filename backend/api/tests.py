from flask import jsonify
from datetime import datetime, timezone
from api import blueprint
from auth import login_required
from models.academic import Assignment

@blueprint.route("/tests", methods=["GET"])
@login_required()
def list_tests(user):
    if not user.klass:
        return jsonify([])

    subject_ids = [s.id for s in user.klass.subjects]
    tests = (
        Assignment.query
        .filter(
            Assignment.subject_id.in_(subject_ids),
            Assignment.type == "test",
            Assignment.due_date >= datetime.now(timezone.utc),
        )
        .order_by(Assignment.due_date)
        .all()
    )

    return jsonify([t.to_dict() for t in tests])
