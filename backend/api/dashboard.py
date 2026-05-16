from flask import jsonify
from datetime import datetime, timezone, timedelta
from api import blueprint
from auth import login_required
from models.academic import Assignment, Grade

@blueprint.route("/dashboard", methods=["GET"])
@login_required()
def dashboard(user):
    now = datetime.now(timezone.utc)
    today_end = now.replace(hour=23, minute=59, second=59)
    week_end = now + timedelta(days=7)

    if user.klass:
        subject_ids = [s.id for s in user.klass.subjects]
        assignments = Assignment.query.filter(
            Assignment.subject_id.in_(subject_ids),
            Assignment.due_date >= now,
        ).order_by(Assignment.due_date).all()
    else:
        assignments = []

    due_today = [a for a in assignments if a.due_date <= today_end]
    due_this_week = [a for a in assignments if today_end < a.due_date <= week_end]

    grades = Grade.query.filter_by(student_id=user.id).all()
    gpa = round(sum(g.score for g in grades) / len(grades), 2) if grades else 0.0

    return jsonify({
        "due_today": [a.to_dict() for a in due_today],
        "due_this_week": [a.to_dict() for a in due_this_week],
        "gpa": gpa,
    })
