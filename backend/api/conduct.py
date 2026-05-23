from flask import jsonify
from sqlalchemy import func
from api import blueprint, err, ok
from auth import login_required
from models import db
from models.conduct import ConductEvent
from models.user import User

CATEGORIES = ["participation", "behaviour", "assignments", "absences"]

@blueprint.route("/conduct", methods=["GET"])
@login_required()
def get_conduct(user):
    events = (
        ConductEvent.query
        .filter_by(student_id=user.id)
        .order_by(ConductEvent.date.desc())
        .all()
    )

    positive  = sum(e.points for e in events if e.points > 0)
    negative  = sum(e.points for e in events if e.points < 0)
    excused   = sum(1        for e in events if e.points == 0)
    total     = positive + negative

    # Group by subject for the table
    by_subject = {}
    for e in events:
        subj = e.subject.name if e.subject else "Unknown"
        if subj not in by_subject:
            by_subject[subj] = {c: 0 for c in CATEGORIES}
        if e.category in by_subject[subj]:
            by_subject[subj][e.category] += e.points

    subject_rows = [
        {"subject": subj, **cats}
        for subj, cats in sorted(by_subject.items())
    ]

    # Class rank (conduct points among classmates)
    rank = None
    if user.class_id:
        classmates = User.query.filter_by(class_id=user.class_id, role="student").all()
        totals = {}
        for cm in classmates:
            pts = db.session.query(func.sum(ConductEvent.points))\
                .filter_by(student_id=cm.id).scalar() or 0
            totals[cm.id] = int(pts)
        sorted_ids = sorted(totals, key=lambda x: totals[x], reverse=True)
        rank = sorted_ids.index(user.id) + 1 if user.id in sorted_ids else None

    return jsonify({
        "total_points": total,
        "positive": positive,
        "negative": negative,
        "excused": excused,
        "class_rank": rank,
        "subject_rows": subject_rows,
        "events": [e.to_dict() for e in events],
    })
