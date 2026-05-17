from models import db
from datetime import datetime, timezone


class Notification(db.Model):
    __tablename__ = "notifications"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type       = db.Column(db.String(32), default="info")   # info | deadline | grade | study
    title      = db.Column(db.String(200), nullable=False)
    body       = db.Column(db.Text, default="")
    link       = db.Column(db.String(200))
    read       = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id":         self.id,
            "type":       self.type,
            "title":      self.title,
            "body":       self.body,
            "link":       self.link,
            "read":       self.read,
            "created_at": self.created_at.isoformat(),
        }
