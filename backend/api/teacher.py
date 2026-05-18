from flask import request, jsonify
from api import blueprint
from auth import login_required
from models import db
from models.school import Subject, Class
from models.academic import Assignment, Grade
from models.conduct import ConductEvent
from models.user import User
from datetime import datetime, timezone


def _teacher_subjects(teacher):
    return Subject.query.filter_by(teacher_id=teacher.id).all()


def _teacher_subject_ids(teacher):
    return [s.id for s in _teacher_subjects(teacher)]


def _owns_assignment(teacher, assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    if a.subject_id not in _teacher_subject_ids(teacher):
        return None, (jsonify({"error": "forbidden"}), 403)
    return a, None


# ── Overview ─────────────────────────────────────────────────────────────────

@blueprint.route("/teacher/overview", methods=["GET"])
@login_required(roles=["teacher"])
def teacher_overview(user):
    subject_ids = _teacher_subject_ids(user)
    class_ids = list({s.class_id for s in _teacher_subjects(user)})
    student_count = User.query.filter(User.class_id.in_(class_ids), User.role == "student").count()
    assignment_count = Assignment.query.filter(Assignment.subject_id.in_(subject_ids)).count()
    graded = Grade.query.join(Assignment).filter(Assignment.subject_id.in_(subject_ids)).count()
    ungraded_assignments = (
        Assignment.query
        .filter(Assignment.subject_id.in_(subject_ids))
        .outerjoin(Grade)
        .filter(Grade.id == None)
        .count()
    )
    return jsonify({
        "subjects":    len(subject_ids),
        "classes":     len(class_ids),
        "students":    student_count,
        "assignments": assignment_count,
        "ungraded":    ungraded_assignments,
    })


# ── Subjects & classes ────────────────────────────────────────────────────────

@blueprint.route("/teacher/subjects", methods=["GET"])
@login_required(roles=["teacher"])
def teacher_subjects(user):
    subjects = _teacher_subjects(user)
    return jsonify([{
        "id":           s.id,
        "name":         s.name,
        "class_id":     s.class_id,
        "class_name":   s.klass.name,
        "student_count": len(s.klass.students),
    } for s in subjects])


@blueprint.route("/teacher/classes", methods=["GET"])
@login_required(roles=["teacher"])
def teacher_classes(user):
    subjects = _teacher_subjects(user)
    classes = {}
    for s in subjects:
        if s.class_id not in classes:
            classes[s.class_id] = {
                "id":       s.class_id,
                "name":     s.klass.name,
                "year":     s.klass.grade_year,
                "students": len(s.klass.students),
                "subjects": [],
            }
        classes[s.class_id]["subjects"].append({"id": s.id, "name": s.name})
    return jsonify(list(classes.values()))


@blueprint.route("/teacher/classes/<int:class_id>/students", methods=["GET"])
@login_required(roles=["teacher"])
def teacher_class_students(user, class_id):
    # Verify teacher teaches in this class
    my_class_ids = {s.class_id for s in _teacher_subjects(user)}
    if class_id not in my_class_ids:
        return jsonify({"error": "forbidden"}), 403

    klass = Class.query.get_or_404(class_id)
    subject_ids = _teacher_subject_ids(user)

    students = []
    for s in klass.students:
        grades = (
            Grade.query
            .join(Assignment)
            .filter(Grade.student_id == s.id, Assignment.subject_id.in_(subject_ids))
            .all()
        )
        avg = round(sum(g.score for g in grades) / len(grades), 1) if grades else None
        students.append({**s.to_dict(), "grade_avg": avg, "grade_count": len(grades)})

    return jsonify({"class": klass.name, "students": students})


# ── Assignments ───────────────────────────────────────────────────────────────

@blueprint.route("/teacher/assignments", methods=["GET"])
@login_required(roles=["teacher"])
def teacher_assignments(user):
    subject_ids = _teacher_subject_ids(user)
    assignments = (
        Assignment.query
        .filter(Assignment.subject_id.in_(subject_ids))
        .order_by(Assignment.due_date.desc())
        .all()
    )
    result = []
    for a in assignments:
        graded = Grade.query.filter_by(assignment_id=a.id).count()
        total = len(a.subject.klass.students)
        result.append({
            "id":          a.id,
            "title":       a.title,
            "description": a.description,
            "type":        a.type,
            "due_date":    a.due_date.isoformat(),
            "subject_id":  a.subject_id,
            "subject_name": a.subject.name,
            "class_name":  a.subject.klass.name,
            "graded":      graded,
            "total":       total,
            "created_at":  a.created_at.isoformat(),
        })
    return jsonify(result)


@blueprint.route("/teacher/assignments", methods=["POST"])
@login_required(roles=["teacher"])
def create_assignment(user):
    data = request.get_json(silent=True) or {}
    subject_id = data.get("subject_id")
    if subject_id not in _teacher_subject_ids(user):
        return jsonify({"error": "forbidden"}), 403

    due_raw = data.get("due_date")
    if not due_raw:
        return jsonify({"error": "due_date required"}), 400
    try:
        due_date = datetime.fromisoformat(due_raw.replace("Z", "+00:00"))
    except ValueError:
        return jsonify({"error": "invalid due_date"}), 400

    a = Assignment(
        subject_id=subject_id,
        title=data.get("title", "").strip(),
        description=data.get("description", "").strip(),
        type=data.get("type", "homework"),
        due_date=due_date,
    )
    if not a.title:
        return jsonify({"error": "title required"}), 400
    db.session.add(a)
    db.session.commit()
    return jsonify({"id": a.id, "title": a.title}), 201


@blueprint.route("/teacher/assignments/<int:assignment_id>", methods=["PATCH"])
@login_required(roles=["teacher"])
def update_assignment(user, assignment_id):
    a, err = _owns_assignment(user, assignment_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    if "title" in data:
        a.title = data["title"].strip()
    if "description" in data:
        a.description = data["description"].strip()
    if "type" in data and data["type"] in ("homework", "test", "project"):
        a.type = data["type"]
    if "due_date" in data:
        try:
            a.due_date = datetime.fromisoformat(data["due_date"].replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "invalid due_date"}), 400
    db.session.commit()
    return jsonify({"ok": True})


@blueprint.route("/teacher/assignments/<int:assignment_id>", methods=["DELETE"])
@login_required(roles=["teacher"])
def delete_assignment(user, assignment_id):
    a, err = _owns_assignment(user, assignment_id)
    if err:
        return err
    Grade.query.filter_by(assignment_id=a.id).delete()
    db.session.delete(a)
    db.session.commit()
    return jsonify({"ok": True})


# ── Grades ────────────────────────────────────────────────────────────────────

@blueprint.route("/teacher/assignments/<int:assignment_id>/grades", methods=["GET"])
@login_required(roles=["teacher"])
def assignment_grades(user, assignment_id):
    a, err = _owns_assignment(user, assignment_id)
    if err:
        return err

    students = a.subject.klass.students
    grades_map = {g.student_id: g for g in a.grades}

    return jsonify({
        "assignment": {"id": a.id, "title": a.title, "type": a.type, "max": 10},
        "students": [{
            "id":    s.id,
            "name":  s.name,
            "score": grades_map[s.id].score if s.id in grades_map else None,
            "grade_id": grades_map[s.id].id if s.id in grades_map else None,
        } for s in students],
    })


@blueprint.route("/teacher/grades", methods=["POST"])
@login_required(roles=["teacher"])
def set_grade(user):
    data = request.get_json(silent=True) or {}
    assignment_id = data.get("assignment_id")
    student_id    = data.get("student_id")
    score         = data.get("score")
    quarter       = data.get("quarter", 1)

    if score is None:
        return jsonify({"error": "score required"}), 400
    try:
        score = float(score)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid score"}), 400
    if not (0 <= score <= 10):
        return jsonify({"error": "score must be 0–10"}), 400

    a, err = _owns_assignment(user, assignment_id)
    if err:
        return err

    # Verify student is in this class
    student_ids = {s.id for s in a.subject.klass.students}
    if student_id not in student_ids:
        return jsonify({"error": "student not in class"}), 403

    existing = Grade.query.filter_by(assignment_id=assignment_id, student_id=student_id).first()
    if existing:
        existing.score = score
    else:
        db.session.add(Grade(
            assignment_id=assignment_id,
            student_id=student_id,
            score=score,
            quarter=quarter,
        ))
    db.session.commit()
    return jsonify({"ok": True})


# ── Conduct ───────────────────────────────────────────────────────────────────

@blueprint.route("/teacher/conduct", methods=["POST"])
@login_required(roles=["teacher"])
def log_conduct(user):
    data = request.get_json(silent=True) or {}
    subject_id = data.get("subject_id")
    student_id = data.get("student_id")
    points     = data.get("points")
    category   = data.get("category", "behaviour")
    reason     = data.get("reason", "")

    if subject_id not in _teacher_subject_ids(user):
        return jsonify({"error": "forbidden"}), 403
    if points is None:
        return jsonify({"error": "points required"}), 400

    ev = ConductEvent(
        student_id=student_id,
        teacher_id=user.id,
        subject_id=subject_id,
        points=int(points),
        category=category,
        reason=reason,
    )
    db.session.add(ev)
    db.session.commit()
    return jsonify({"id": ev.id}), 201
