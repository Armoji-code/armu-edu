import secrets
from datetime import datetime, timezone
from models import db


class Meeting(db.Model):
    __tablename__ = "meetings"

    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)
    host_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    class_id   = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=True)
    room_code  = db.Column(db.String(8), unique=True, nullable=False,
                           default=lambda: secrets.token_urlsafe(6))
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at   = db.Column(db.DateTime, nullable=True)

    host = db.relationship("User", foreign_keys=[host_id])

    def to_dict(self, participant_count=0):
        return {
            "id":                self.id,
            "title":             self.title,
            "host_id":           self.host_id,
            "host_name":         self.host.name if self.host else "",
            "class_id":          self.class_id,
            "room_code":         self.room_code,
            "is_active":         self.is_active,
            "created_at":        self.created_at.isoformat(),
            "participant_count": participant_count,
        }
