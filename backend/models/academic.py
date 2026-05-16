from models import db
from datetime import datetime, timezone

class Assignment(db.Model):
    __tablename__ = "assignments"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, default="")
    due_date = db.Column(db.DateTime, nullable=False)
    type = db.Column(db.Enum("homework", "test", "project", name="assignment_type"), nullable=False, default="homework")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    subject = db.relationship("Subject", back_populates="assignments")
    grades = db.relationship("Grade", back_populates="assignment")

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "subject_name": self.subject.name if self.subject else None,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat(),
            "type": self.type,
        }


class Grade(db.Model):
    __tablename__ = "grades"

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignments.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    score = db.Column(db.Float, nullable=False)
    quarter = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    assignment = db.relationship("Assignment", back_populates="grades")
    student = db.relationship("User", foreign_keys=[student_id])

    @property
    def letter(self):
        if self.score >= 90: return "A"
        if self.score >= 80: return "B"
        if self.score >= 70: return "C"
        if self.score >= 60: return "D"
        return "F"

    def to_dict(self):
        return {
            "id": self.id,
            "assignment_id": self.assignment_id,
            "score": self.score,
            "letter": self.letter,
            "quarter": self.quarter,
            "created_at": self.created_at.isoformat(),
        }


class SchedulePeriod(db.Model):
    __tablename__ = "schedule_periods"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Mon … 4=Fri
    period_number = db.Column(db.Integer, nullable=False)  # 1–8
    start_time = db.Column(db.String(5), nullable=False)   # "08:00"
    end_time = db.Column(db.String(5), nullable=False)     # "08:45"

    subject = db.relationship("Subject", back_populates="periods")

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "subject_name": self.subject.name if self.subject else None,
            "day_of_week": self.day_of_week,
            "period_number": self.period_number,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
