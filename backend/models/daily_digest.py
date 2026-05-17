from models import db
from datetime import datetime, timezone, date


class DailyDigest(db.Model):
    __tablename__ = "daily_digests"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date         = db.Column(db.Date, nullable=False)
    content      = db.Column(db.Text, nullable=False)
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("user_id", "date"),)

    def to_dict(self):
        return {
            "content":      self.content,
            "generated_at": self.generated_at.isoformat(),
            "cached":       True,
        }
