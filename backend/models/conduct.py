from models import db
from datetime import datetime, timezone

class ConductEvent(db.Model):
    __tablename__ = "conduct_events"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    # +3 excellent, +1 good, -1 issue, 0 excused
    points = db.Column(db.Integer, nullable=False)
    category = db.Column(db.Enum("participation", "behaviour", "assignments", "absences", name="conduct_category"), nullable=False)
    reason = db.Column(db.String(300), default="")
    date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    student = db.relationship("User", foreign_keys=[student_id])
    teacher = db.relationship("User", foreign_keys=[teacher_id])
    subject = db.relationship("Subject")

    def to_dict(self):
        return {
            "id": self.id,
            "points": self.points,
            "category": self.category,
            "reason": self.reason,
            "subject_name": self.subject.name if self.subject else None,
            "teacher_name": self.teacher.name if self.teacher else None,
            "date": self.date.isoformat(),
        }
