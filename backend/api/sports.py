from flask import request, jsonify, current_app
from datetime import datetime, timezone
from api import blueprint, err, ok
from auth import login_required
from models import db
from models.sports import SportsTeam, SportsGame, SportsJoinRequest, sports_team_members
from models.user import User


def _school_id(user):
    return user.school_id


def _notify(user_id, title, body="", type="info", link=None):
    """Send a notification — deferred socketio import avoids circular imports."""
    from app import socketio as _socketio
    from models.notification import Notification
    n = Notification(user_id=user_id, title=title, body=body, type=type, link=link)
    db.session.add(n)
    db.session.flush()
    try:
        _socketio.emit("notification", n.to_dict(), room=f"user_{user_id}")
    except Exception:
        pass
    try:
        from api.push import send_web_push
        send_web_push(current_app._get_current_object(), user_id, title, body, link or "/")
    except Exception:
        pass


def _notify_admins(school_id, title, body="", link=None):
    admins = User.query.filter_by(school_id=school_id, role="admin").all()
    for admin in admins:
        _notify(admin.id, title, body, type="info", link=link)


# ── Student: read ─────────────────────────────────────────────────────────────

@blueprint.route("/sports/teams", methods=["GET"])
@login_required()
def get_sports_teams(user):
    teams = SportsTeam.query.filter_by(school_id=_school_id(user)).order_by(SportsTeam.sport, SportsTeam.name).all()

    # Fetch this user's pending requests in one query
    pending_ids = {
        r.team_id for r in
        SportsJoinRequest.query.filter_by(user_id=user.id, status="pending").all()
    }

    return jsonify([
        t.to_dict(user_id=user.id, join_request_status="pending" if t.id in pending_ids else None)
        for t in teams
    ])


@blueprint.route("/sports/games", methods=["GET"])
@login_required()
def get_sports_games(user):
    team_id = request.args.get("team_id", type=int)
    status  = request.args.get("status")

    q = (
        SportsGame.query
        .join(SportsTeam, SportsGame.team_id == SportsTeam.id)
        .filter(SportsTeam.school_id == _school_id(user))
    )
    if team_id:
        q = q.filter(SportsGame.team_id == team_id)
    if status:
        q = q.filter(SportsGame.status == status)

    return jsonify([g.to_dict() for g in q.order_by(SportsGame.date).all()])


# ── Student: join request ─────────────────────────────────────────────────────

@blueprint.route("/sports/teams/<int:team_id>/join", methods=["POST"])
@login_required()
def request_join_team(user, team_id):
    team = SportsTeam.query.filter_by(id=team_id, school_id=_school_id(user)).first()
    if not team:
        return err("Team not found", 404)
    if user in team.members:
        return err("Already a member")

    existing = SportsJoinRequest.query.filter_by(team_id=team_id, user_id=user.id).first()
    if existing:
        if existing.status == "pending":
            return ok(status="pending")
        # Re-open a previously denied request
        existing.status = "pending"
        existing.created_at = datetime.now(timezone.utc)
        db.session.commit()
    else:
        req = SportsJoinRequest(team_id=team_id, user_id=user.id, status="pending")
        db.session.add(req)
        db.session.commit()

    _notify_admins(
        school_id=_school_id(user),
        title=f"Join request: {team.name}",
        body=f"{user.name} wants to join {team.name} ({team.sport}).",
        link="/admin/sports",
    )
    return ok(status="pending")


@blueprint.route("/sports/teams/<int:team_id>/join", methods=["DELETE"])
@login_required()
def cancel_join_request(user, team_id):
    team = SportsTeam.query.filter_by(id=team_id, school_id=_school_id(user)).first()
    if not team:
        return err("Team not found", 404)

    # Allow leaving if already a member
    if user in team.members:
        team.members.remove(user)
        db.session.commit()
        return ok(status=None)

    req = SportsJoinRequest.query.filter_by(team_id=team_id, user_id=user.id, status="pending").first()
    if req:
        db.session.delete(req)
        db.session.commit()
    return ok(status=None)


# ── Admin: CRUD teams ─────────────────────────────────────────────────────────

@blueprint.route("/admin/sports/teams", methods=["GET"])
@login_required(roles=["admin"])
def admin_list_sports_teams(user):
    teams = SportsTeam.query.filter_by(school_id=_school_id(user)).order_by(SportsTeam.sport, SportsTeam.name).all()
    result = []
    for t in teams:
        d = t.to_dict()
        d["games"] = [g.to_dict() for g in t.games]
        result.append(d)
    return jsonify(result)


@blueprint.route("/admin/sports/teams", methods=["POST"])
@login_required(roles=["admin"])
def admin_create_sports_team(user):
    data = request.get_json(force=True)
    name  = (data.get("name") or "").strip()
    sport = (data.get("sport") or "").strip()
    if not name or not sport:
        return err("name and sport are required")
    team = SportsTeam(
        school_id=_school_id(user),
        name=name, sport=sport,
        description=(data.get("description") or "").strip(),
        coach_id=data.get("coach_id") or None,
    )
    db.session.add(team)
    db.session.commit()
    return ok(team=team.to_dict())


@blueprint.route("/admin/sports/teams/<int:team_id>", methods=["PUT"])
@login_required(roles=["admin"])
def admin_update_sports_team(user, team_id):
    team = SportsTeam.query.filter_by(id=team_id, school_id=_school_id(user)).first()
    if not team:
        return err("Team not found", 404)
    data = request.get_json(force=True)
    if "name" in data:        team.name        = data["name"].strip()
    if "sport" in data:       team.sport       = data["sport"].strip()
    if "description" in data: team.description = data["description"].strip()
    if "coach_id" in data:    team.coach_id    = data["coach_id"] or None
    db.session.commit()
    return ok(team=team.to_dict())


@blueprint.route("/admin/sports/teams/<int:team_id>", methods=["DELETE"])
@login_required(roles=["admin"])
def admin_delete_sports_team(user, team_id):
    team = SportsTeam.query.filter_by(id=team_id, school_id=_school_id(user)).first()
    if not team:
        return err("Team not found", 404)
    db.session.delete(team)
    db.session.commit()
    return ok()


# ── Admin: join requests ──────────────────────────────────────────────────────

@blueprint.route("/admin/sports/join-requests", methods=["GET"])
@login_required(roles=["admin"])
def admin_list_join_requests(user):
    reqs = (
        SportsJoinRequest.query
        .join(SportsTeam, SportsJoinRequest.team_id == SportsTeam.id)
        .filter(SportsTeam.school_id == _school_id(user))
        .filter(SportsJoinRequest.status == "pending")
        .order_by(SportsJoinRequest.created_at.desc())
        .all()
    )
    return jsonify([r.to_dict() for r in reqs])


@blueprint.route("/admin/sports/join-requests/<int:req_id>/approve", methods=["POST"])
@login_required(roles=["admin"])
def admin_approve_join_request(user, req_id):
    req = (
        SportsJoinRequest.query
        .join(SportsTeam, SportsJoinRequest.team_id == SportsTeam.id)
        .filter(SportsJoinRequest.id == req_id, SportsTeam.school_id == _school_id(user))
        .first()
    )
    if not req:
        return err("Request not found", 404)

    student = User.query.get(req.user_id)
    team    = req.team

    if student and student not in team.members:
        team.members.append(student)

    req.status = "approved"
    db.session.commit()

    _notify(
        req.user_id,
        title=f"Joined {team.name}!",
        body=f"Your request to join {team.name} ({team.sport}) was approved.",
        type="info",
        link="/sports",
    )
    return ok()


@blueprint.route("/admin/sports/join-requests/<int:req_id>/deny", methods=["POST"])
@login_required(roles=["admin"])
def admin_deny_join_request(user, req_id):
    req = (
        SportsJoinRequest.query
        .join(SportsTeam, SportsJoinRequest.team_id == SportsTeam.id)
        .filter(SportsJoinRequest.id == req_id, SportsTeam.school_id == _school_id(user))
        .first()
    )
    if not req:
        return err("Request not found", 404)

    team_name = req.team.name if req.team else "the team"
    sport     = req.team.sport if req.team else ""
    req.status = "denied"
    db.session.commit()

    _notify(
        req.user_id,
        title=f"Request denied: {team_name}",
        body=f"Your request to join {team_name} ({sport}) was not approved.",
        type="info",
        link="/sports",
    )
    return ok()


# ── Admin: CRUD games ─────────────────────────────────────────────────────────

@blueprint.route("/admin/sports/games", methods=["POST"])
@login_required(roles=["admin"])
def admin_create_sports_game(user):
    data     = request.get_json(force=True)
    team_id  = data.get("team_id")
    opponent = (data.get("opponent") or "").strip()
    date_str = data.get("date")
    if not team_id or not opponent or not date_str:
        return err("team_id, opponent, and date are required")
    team = SportsTeam.query.filter_by(id=team_id, school_id=_school_id(user)).first()
    if not team:
        return err("Team not found", 404)
    try:
        date = datetime.fromisoformat(date_str)
    except ValueError:
        return err("Invalid date format")
    game = SportsGame(
        team_id=team_id, opponent=opponent, date=date,
        location=(data.get("location") or "").strip(),
        status=data.get("status", "upcoming"),
        home_score=data.get("home_score"),
        away_score=data.get("away_score"),
    )
    db.session.add(game)
    db.session.commit()
    return ok(game=game.to_dict())


@blueprint.route("/admin/sports/games/<int:game_id>", methods=["PUT"])
@login_required(roles=["admin"])
def admin_update_sports_game(user, game_id):
    game = (
        SportsGame.query
        .join(SportsTeam, SportsGame.team_id == SportsTeam.id)
        .filter(SportsGame.id == game_id, SportsTeam.school_id == _school_id(user))
        .first()
    )
    if not game:
        return err("Game not found", 404)
    data = request.get_json(force=True)
    if "opponent" in data:   game.opponent   = data["opponent"].strip()
    if "location" in data:   game.location   = data["location"].strip()
    if "status" in data:     game.status     = data["status"]
    if "home_score" in data: game.home_score = data["home_score"]
    if "away_score" in data: game.away_score = data["away_score"]
    if "date" in data:
        try:
            game.date = datetime.fromisoformat(data["date"])
        except ValueError:
            return err("Invalid date format")
    db.session.commit()
    return ok(game=game.to_dict())


@blueprint.route("/admin/sports/games/<int:game_id>", methods=["DELETE"])
@login_required(roles=["admin"])
def admin_delete_sports_game(user, game_id):
    game = (
        SportsGame.query
        .join(SportsTeam, SportsGame.team_id == SportsTeam.id)
        .filter(SportsGame.id == game_id, SportsTeam.school_id == _school_id(user))
        .first()
    )
    if not game:
        return err("Game not found", 404)
    db.session.delete(game)
    db.session.commit()
    return ok()
