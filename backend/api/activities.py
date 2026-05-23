from flask import jsonify
from datetime import datetime, timezone
from api import blueprint, err, ok
from auth import login_required
from models.social import Activity, ActivityEvent, CommunityService, activity_enrollments
from models import db

SERVICE_GOAL_HOURS = 40

@blueprint.route("/activities", methods=["GET"])
@login_required()
def get_activities(user):
    enrolled = (
        Activity.query
        .join(activity_enrollments, Activity.id == activity_enrollments.c.activity_id)
        .filter(activity_enrollments.c.user_id == user.id)
        .all()
    )

    now = datetime.now(timezone.utc)
    result = []
    for act in enrolled:
        upcoming = (
            ActivityEvent.query
            .filter_by(activity_id=act.id)
            .filter(ActivityEvent.date >= now)
            .order_by(ActivityEvent.date)
            .limit(5)
            .all()
        )
        result.append({**act.to_dict(), "upcoming_events": [e.to_dict() for e in upcoming]})

    return jsonify(result)


@blueprint.route("/community-service", methods=["GET"])
@login_required()
def get_community_service(user):
    logs = (
        CommunityService.query
        .filter_by(user_id=user.id)
        .order_by(CommunityService.date.desc())
        .all()
    )

    total_hours = sum(e.hours for e in logs)
    orgs = len({e.organization for e in logs})

    now = datetime.now(timezone.utc)
    this_month = sum(
        e.hours for e in logs
        if e.date.year == now.year and e.date.month == now.month
    )

    return jsonify({
        "total_hours": total_hours,
        "goal_hours": SERVICE_GOAL_HOURS,
        "organizations": orgs,
        "this_month_hours": this_month,
        "entries": [e.to_dict() for e in logs],
    })
