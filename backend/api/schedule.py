from flask import jsonify
from api import blueprint, err, ok
from auth import login_required
from models.academic import SchedulePeriod

@blueprint.route("/schedule", methods=["GET"])
@login_required()
def get_schedule(user):
    if not user.class_id:
        return jsonify([])

    periods = (
        SchedulePeriod.query
        .filter_by(class_id=user.class_id)
        .order_by(SchedulePeriod.day_of_week, SchedulePeriod.period_number)
        .all()
    )

    return jsonify([p.to_dict() for p in periods])
