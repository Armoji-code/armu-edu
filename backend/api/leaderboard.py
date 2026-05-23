from flask import jsonify
from sqlalchemy import func
from api import blueprint, err, ok
from auth import login_required
from models import db
from models.user import User
from models.academic import Grade
from models.conduct import ConductEvent
from models.social import Message


@blueprint.route("/leaderboard", methods=["GET"])
@login_required()
def get_leaderboard(user):
    if not user.class_id:
        return jsonify({"streaks": [], "ontime": [], "helpful": [], "conduct": []})

    students = User.query.filter_by(class_id=user.class_id, role="student").all()

    # Pre-fetch aggregates in bulk to avoid N+1 queries
    grade_counts = dict(
        db.session.query(Grade.student_id, func.count(Grade.id))
        .filter(Grade.student_id.in_([s.id for s in students]))
        .group_by(Grade.student_id)
        .all()
    )
    avg_scores = dict(
        db.session.query(Grade.student_id, func.avg(Grade.score))
        .filter(Grade.student_id.in_([s.id for s in students]))
        .group_by(Grade.student_id)
        .all()
    )
    msg_counts = dict(
        db.session.query(Message.sender_id, func.count(Message.id))
        .filter(Message.sender_id.in_([s.id for s in students]))
        .group_by(Message.sender_id)
        .all()
    )
    conduct_totals = dict(
        db.session.query(ConductEvent.student_id, func.sum(ConductEvent.points))
        .filter(ConductEvent.student_id.in_([s.id for s in students]))
        .group_by(ConductEvent.student_id)
        .all()
    )

    def entry(s, score, **extra):
        display = s.name or s.email
        initials = "".join(w[0] for w in display.split()[:2]).upper()
        return {"id": s.id, "name": display, "initials": initials,
                "me": s.id == user.id, "score": score, **extra}

    streaks  = sorted([entry(s, grade_counts.get(s.id, 0)) for s in students],
                      key=lambda x: x["score"], reverse=True)
    ontime   = sorted([entry(s, round(avg_scores.get(s.id) or 0), suffix="%") for s in students],
                      key=lambda x: x["score"], reverse=True)
    helpful  = sorted([entry(s, msg_counts.get(s.id, 0)) for s in students],
                      key=lambda x: x["score"], reverse=True)

    conduct_list = []
    for s in students:
        pts = int(conduct_totals.get(s.id) or 0)
        conduct_list.append(entry(
            s, pts,
            prefix="+" if pts >= 0 else "",
            negative=pts < 0,
        ))
    conduct_list.sort(key=lambda x: x["score"], reverse=True)

    return jsonify({
        "streaks": streaks,
        "ontime":  ontime,
        "helpful": helpful,
        "conduct": conduct_list,
    })
