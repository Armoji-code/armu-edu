from models import db

class School(db.Model):
    __tablename__ = "schools"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    # JSON blob: ollama models, loan periods, etc.
    settings = db.Column(db.JSON, default=dict)

    users = db.relationship("User", back_populates="school")
    classes = db.relationship("Class", back_populates="school")
    books = db.relationship("Book", back_populates="school")


class Class(db.Model):
    __tablename__ = "classes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    grade_year = db.Column(db.Integer, nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)

    school = db.relationship("School", back_populates="classes")
    students = db.relationship("User", back_populates="klass", foreign_keys="User.class_id")
    subjects = db.relationship("Subject", back_populates="klass")


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    klass = db.relationship("Class", back_populates="subjects")
    teacher = db.relationship("User", foreign_keys=[teacher_id])
    assignments = db.relationship("Assignment", back_populates="subject")
    periods = db.relationship("SchedulePeriod", back_populates="subject")
