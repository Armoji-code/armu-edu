"""Run once to create tables and a test student account."""
from app import create_app
from models import db
from models.school import School, Class, Subject
from models.user import User

app = create_app()

with app.app_context():
    db.create_all()

    if not School.query.first():
        school = School(name="Test School")
        db.session.add(school)
        db.session.flush()

        klass = Class(name="10A", grade_year=10, school_id=school.id)
        db.session.add(klass)
        db.session.flush()

        student = User(name="Armin Test", email="student@test.lt", role="student",
                       school_id=school.id, class_id=klass.id)
        student.set_password("password")
        db.session.add(student)

        teacher = User(name="Teacher Demo", email="teacher@test.lt", role="teacher",
                       school_id=school.id)
        teacher.set_password("password")
        db.session.add(teacher)
        db.session.flush()

        math = Subject(name="Mathematics", class_id=klass.id, teacher_id=teacher.id)
        db.session.add(math)

        db.session.commit()
        print("Seeded: school, class 10A, student@test.lt, teacher@test.lt (password: password)")
    else:
        print("Already seeded.")
