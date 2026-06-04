from models import db
from datetime import datetime, timezone

sports_team_members = db.Table(
    "sports_team_members",
    db.Column("team_id", db.Integer, db.ForeignKey("sports_teams.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
)


class SportsTeam(db.Model):
    __tablename__ = "sports_teams"

    id          = db.Column(db.Integer, primary_key=True)
    school_id   = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    name        = db.Column(db.String(150), nullable=False)
    sport       = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    coach_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    coach   = db.relationship("User", foreign_keys=[coach_id])
    members = db.relationship("User", secondary=sports_team_members)
    games   = db.relationship("SportsGame", back_populates="team",
                              cascade="all, delete-orphan", order_by="SportsGame.date")

    def to_dict(self, user_id=None, join_request_status=None):
        return {
            "id":                   self.id,
            "name":                 self.name,
            "sport":                self.sport,
            "description":          self.description,
            "coach_name":           self.coach.name if self.coach else None,
            "member_count":         len(self.members),
            "is_member":            user_id in {m.id for m in self.members} if user_id else False,
            "join_request_status":  join_request_status,
        }


class SportsGame(db.Model):
    __tablename__ = "sports_games"

    id         = db.Column(db.Integer, primary_key=True)
    team_id    = db.Column(db.Integer, db.ForeignKey("sports_teams.id"), nullable=False)
    date       = db.Column(db.DateTime, nullable=False)
    opponent   = db.Column(db.String(200), nullable=False)
    location   = db.Column(db.String(300), default="")
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    status     = db.Column(
        db.Enum("upcoming", "completed", "cancelled", name="game_status"),
        default="upcoming", nullable=False,
    )

    team = db.relationship("SportsTeam", back_populates="games")

    def to_dict(self):
        return {
            "id":         self.id,
            "team_id":    self.team_id,
            "team_name":  self.team.name if self.team else None,
            "date":       self.date.isoformat(),
            "opponent":   self.opponent,
            "location":   self.location,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "status":     self.status,
        }


class SportsJoinRequest(db.Model):
    __tablename__ = "sports_join_requests"
    __table_args__ = (db.UniqueConstraint("team_id", "user_id"),)

    id         = db.Column(db.Integer, primary_key=True)
    team_id    = db.Column(db.Integer, db.ForeignKey("sports_teams.id"), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status     = db.Column(db.String(20), default="pending", nullable=False)  # pending/approved/denied
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    team = db.relationship("SportsTeam")
    user = db.relationship("User")

    def to_dict(self):
        return {
            "id":         self.id,
            "team_id":    self.team_id,
            "team_name":  self.team.name if self.team else None,
            "user_id":    self.user_id,
            "user_name":  self.user.name if self.user else None,
            "status":     self.status,
            "created_at": self.created_at.isoformat(),
        }
