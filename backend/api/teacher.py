from flask import request, jsonify, current_app
from api import blueprint, err, ok
from auth import login_required
from models import db
from models.school import Subject, Class
from models.academic import Assignment, Grade, SchedulePeriod
from models.conduct import ConductEvent
from models.notification import Notification
from models.user import User
from datetime import datetime, timezone
import io, csv


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
        return err("forbidden", 403)

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
        return err("forbidden", 403)

    due_raw = data.get("due_date")
    if not due_raw:
        return err("due_date required", 400)
    try:
        due_date = datetime.fromisoformat(due_raw.replace("Z", "+00:00"))
    except ValueError:
        return err("invalid due_date", 400)

    a_type = data.get("type", "homework")
    if a_type not in ("homework", "test", "project"):
        a_type = "homework"
    a = Assignment(
        subject_id=subject_id,
        title=data.get("title", "").strip(),
        description=data.get("description", "").strip(),
        type=a_type,
        due_date=due_date,
    )
    if not a.title:
        return err("title required", 400)
    db.session.add(a)
    db.session.commit()
    return jsonify({"id": a.id, "title": a.title}), 201


@blueprint.route("/teacher/assignments/<int:assignment_id>", methods=["PATCH"])
@login_required(roles=["teacher"])
def update_assignment(user, assignment_id):
    a, e = _owns_assignment(user, assignment_id)
    if e:
        return e
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
            return err("invalid due_date", 400)
    db.session.commit()
    return ok()


@blueprint.route("/teacher/assignments/<int:assignment_id>", methods=["DELETE"])
@login_required(roles=["teacher"])
def delete_assignment(user, assignment_id):
    a, e = _owns_assignment(user, assignment_id)
    if e:
        return e
    Grade.query.filter_by(assignment_id=a.id).delete()
    db.session.delete(a)
    db.session.commit()
    return ok()


# ── Grades ────────────────────────────────────────────────────────────────────

@blueprint.route("/teacher/assignments/<int:assignment_id>/grades", methods=["GET"])
@login_required(roles=["teacher"])
def assignment_grades(user, assignment_id):
    a, e = _owns_assignment(user, assignment_id)
    if e:
        return e

    students = a.subject.klass.students
    grades_map = {g.student_id: g for g in a.grades}

    return jsonify({
        "assignment": {"id": a.id, "title": a.title, "type": a.type, "max": 100},
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
        return err("score required", 400)
    try:
        score = float(score)
    except (TypeError, ValueError):
        return err("invalid score", 400)
    if not (0 <= score <= 100):
        return err("score must be 0–100", 400)

    a, e = _owns_assignment(user, assignment_id)
    if e:
        return e

    # Verify student is in this class
    student_ids = {s.id for s in a.subject.klass.students}
    if student_id not in student_ids:
        return err("student not in class", 403)

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
    return ok()


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
        return err("forbidden", 403)
    if not student_id:
        return err("student_id required", 400)
    if points is None:
        return err("points required", 400)
    try:
        points = int(points)
    except (TypeError, ValueError):
        return err("points must be an integer", 400)
    if not (-100 <= points <= 100):
        return err("points must be between -100 and 100", 400)

    subject = Subject.query.get(subject_id)
    student = User.query.filter_by(id=student_id, class_id=subject.class_id, role="student").first()
    if not student:
        return err("student not found in this class", 404)

    ev = ConductEvent(
        student_id=student_id,
        teacher_id=user.id,
        subject_id=subject_id,
        points=points,
        category=category,
        reason=reason,
    )
    db.session.add(ev)
    db.session.commit()
    return jsonify({"id": ev.id}), 201


# ── Conduct log viewer ────────────────────────────────────────────────────────

@blueprint.route("/teacher/conduct-log", methods=["GET"])
@login_required(roles=["teacher"])
def teacher_conduct_log(user):
    subject_ids = _teacher_subject_ids(user)
    events = (
        ConductEvent.query
        .filter(ConductEvent.teacher_id == user.id)
        .order_by(ConductEvent.date.desc())
        .limit(200)
        .all()
    )
    result = []
    for ev in events:
        result.append({
            "id":           ev.id,
            "student_id":   ev.student_id,
            "student_name": ev.student.name if ev.student else "",
            "subject_name": ev.subject.name if ev.subject else "",
            "class_name":   ev.subject.klass.name if ev.subject and ev.subject.klass else "",
            "points":       ev.points,
            "category":     ev.category,
            "reason":       ev.reason,
            "date":         ev.date.isoformat(),
        })
    return jsonify(result)


# ── Analytics ─────────────────────────────────────────────────────────────────

@blueprint.route("/teacher/analytics", methods=["GET"])
@login_required(roles=["teacher"])
def teacher_analytics(user):
    subjects = _teacher_subjects(user)
    result = []
    for s in subjects:
        students = s.klass.students
        student_ids = [st.id for st in students]
        assignments = Assignment.query.filter_by(subject_id=s.id).all()
        asn_ids = [a.id for a in assignments]

        grades = (
            Grade.query
            .filter(Grade.assignment_id.in_(asn_ids), Grade.student_id.in_(student_ids))
            .all()
        ) if asn_ids else []

        scores = [g.score for g in grades]
        avg = round(sum(scores) / len(scores), 1) if scores else None

        # Distribution buckets: A(90-100), B(75-89), C(60-74), D(50-59), F(<50)
        dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for sc in scores:
            if sc >= 90:   dist["A"] += 1
            elif sc >= 75: dist["B"] += 1
            elif sc >= 60: dist["C"] += 1
            elif sc >= 50: dist["D"] += 1
            else:          dist["F"] += 1

        # Per-student averages
        per_student = []
        for st in students:
            st_scores = [g.score for g in grades if g.student_id == st.id]
            per_student.append({
                "name":  st.name,
                "avg":   round(sum(st_scores)/len(st_scores), 1) if st_scores else None,
                "count": len(st_scores),
            })
        per_student.sort(key=lambda x: (x["avg"] is None, -(x["avg"] or 0)))

        result.append({
            "subject_id":    s.id,
            "subject_name":  s.name,
            "class_name":    s.klass.name,
            "student_count": len(students),
            "assignment_count": len(assignments),
            "graded_count":  len(grades),
            "avg":           avg,
            "distribution":  dist,
            "per_student":   per_student,
        })
    return jsonify(result)


# ── Schedule viewer ───────────────────────────────────────────────────────────

@blueprint.route("/teacher/schedule", methods=["GET"])
@login_required(roles=["teacher"])
def teacher_schedule(user):
    subject_ids = _teacher_subject_ids(user)
    periods = (
        SchedulePeriod.query
        .filter(SchedulePeriod.subject_id.in_(subject_ids))
        .order_by(SchedulePeriod.day_of_week, SchedulePeriod.period_number)
        .all()
    )
    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    by_day = {i: [] for i in range(5)}
    for p in periods:
        if 0 <= p.day_of_week <= 4:
            subj = Subject.query.get(p.subject_id)
            by_day[p.day_of_week].append({
                "id":           p.id,
                "period":       p.period_number,
                "start":        p.start_time,
                "end":          p.end_time,
                "subject_name": subj.name if subj else "",
                "class_name":   subj.klass.name if subj and subj.klass else "",
            })
    return jsonify([
        {"day": DAY_NAMES[i], "day_index": i, "periods": by_day[i]}
        for i in range(5)
    ])


# ── Announce to class ─────────────────────────────────────────────────────────

@blueprint.route("/teacher/announce", methods=["POST"])
@login_required(roles=["teacher"])
def teacher_announce(user):
    from app import socketio  # lazy import — avoids circular dependency at module load
    data = request.get_json(silent=True) or {}
    subject_id = data.get("subject_id")
    title      = (data.get("title") or "").strip()
    body_text  = (data.get("body") or "").strip()

    if subject_id not in _teacher_subject_ids(user):
        return err("forbidden", 403)
    if not title:
        return err("title required", 400)

    subj = Subject.query.get_or_404(subject_id)
    students = subj.klass.students
    notif_ids = []
    for st in students:
        n = Notification(
            user_id=st.id,
            title=title,
            body=body_text,
            type="info",
            link="/homework",
        )
        db.session.add(n)
        db.session.flush()
        socketio.emit("notification", n.to_dict(), room=f"user_{st.id}")
        notif_ids.append(n.id)
    db.session.commit()
    return jsonify({"sent": len(notif_ids)}), 201


# ── Grade export CSV ──────────────────────────────────────────────────────────

@blueprint.route("/teacher/assignments/<int:assignment_id>/grades/export", methods=["GET"])
@login_required(roles=["teacher"])
def export_grades_csv(user, assignment_id):
    a, e = _owns_assignment(user, assignment_id)
    if e:
        return e

    students = a.subject.klass.students
    grades_map = {g.student_id: g.score for g in a.grades}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student", "Score", "Max"])
    for s in students:
        score = grades_map.get(s.id)
        writer.writerow([s.name, "" if score is None else score, 100])

    filename = f"{a.title.replace(' ','_')}_{a.subject.klass.name}_grades.csv"
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
