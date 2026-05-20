"""
Run once to create tables, demo accounts, and sample assignments.
Re-run with --reset-assignments to wipe and recreate assignments only.
"""
import sys
from datetime import datetime, timedelta, timezone
from app import create_app
from models import db
from models.school import School, Class, Subject
from models.user import User
from models.academic import Assignment, Grade

app = create_app()


def seed_assignments(subjects):
    """Wipe all grades + assignments and insert fresh demo data."""
    Grade.query.delete()
    Assignment.query.delete()
    db.session.flush()

    today = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)

    def due(days):
        return today + timedelta(days=days)

    by_name = {s.name: s.id for s in subjects}

    items = [
        # Mathematics
        dict(title="Algebra: Linear Equations",       description="Solve chapters 3–4 exercises.",           type="homework", due=due(3),  subject="Mathematics"),
        dict(title="Quadratic Functions Quiz",         description="Covers vertex form and factoring.",       type="test",     due=due(7),  subject="Mathematics"),
        dict(title="Geometry: Area & Perimeter",       description="Worksheet on polygons and circles.",      type="homework", due=due(10), subject="Mathematics"),
        dict(title="Mid-term Math Test",               description="Chapters 1–6 cumulative test.",           type="test",     due=due(14), subject="Mathematics"),
        # Physics
        dict(title="Newton's Laws — Problem Set",      description="Forces and motion problems, p. 55–58.",   type="homework", due=due(4),  subject="Physics"),
        dict(title="Motion & Forces Test",             description="Kinematics and Newton's laws.",           type="test",     due=due(8),  subject="Physics"),
        dict(title="Lab Report: Pendulum Experiment",  description="Write up the pendulum lab results.",      type="project",  due=due(12), subject="Physics"),
        # Lithuanian
        dict(title="Essay: My Summer",                 description="Write a 300-word personal essay.",        type="homework", due=due(5),  subject="Lithuanian"),
        dict(title="Spelling & Grammar Test",          description="Units 7–9 vocabulary and grammar.",       type="test",     due=due(9),  subject="Lithuanian"),
        dict(title="Short Story Analysis",             description="Analyse the assigned short story.",       type="homework", due=due(15), subject="Lithuanian"),
        # History
        dict(title="WWI Causes — Reading Response",    description="One page on the causes of WWI.",          type="homework", due=due(6),  subject="History"),
        dict(title="WWII Unit Test",                   description="Events from 1939 to 1945.",               type="test",     due=due(11), subject="History"),
    ]

    for item in items:
        sid = by_name.get(item["subject"])
        if not sid:
            continue
        db.session.add(Assignment(
            subject_id=sid,
            title=item["title"],
            description=item["description"],
            type=item["type"],
            due_date=item["due"],
        ))

    db.session.commit()
    print(f"Seeded {len(items)} assignments.")


with app.app_context():
    db.create_all()

    reset_only = "--reset-assignments" in sys.argv

    if reset_only:
        subjects = Subject.query.all()
        seed_assignments(subjects)
    else:
        if not School.query.first():
            school = School(name="Test School")
            db.session.add(school)
            db.session.flush()

            klass = Class(name="10A", grade_year=10, school_id=school.id)
            db.session.add(klass)
            db.session.flush()

            student = User(name="Armin Test", email="student@test.com", role="student",
                           school_id=school.id, class_id=klass.id)
            student.set_password("password")
            db.session.add(student)

            teacher = User(name="Teacher Demo", email="teacher@test.com", role="teacher",
                           school_id=school.id)
            teacher.set_password("password")
            db.session.add(teacher)
            db.session.flush()

            math    = Subject(name="Mathematics", class_id=klass.id, teacher_id=teacher.id)
            physics = Subject(name="Physics",     class_id=klass.id, teacher_id=teacher.id)
            lit     = Subject(name="Lithuanian",  class_id=klass.id, teacher_id=teacher.id)
            hist    = Subject(name="History",     class_id=klass.id, teacher_id=teacher.id)
            db.session.add_all([math, physics, lit, hist])
            db.session.flush()

            seed_assignments([math, physics, lit, hist])
            print("Seeded: school, class 10A, student@test.com, teacher@test.com (password: password)")
        else:
            print("Already seeded. Use --reset-assignments to refresh assignment data.")
