from flask import jsonify
from api import blueprint
from auth import login_required
from models.conduct import ConductEvent

@blueprint.route("/conduct", methods=["GET"])
@login_required()
def get_conduct(user):
    events = (
        ConductEvent.query
        .filter_by(student_id=user.id)
        .order_by(ConductEvent.date.desc())
        .all()
    )
    total = sum(e.points for e in events)
    return jsonify({
        "total_points": total,
        "events": [e.to_dict() for e in events],
    })
