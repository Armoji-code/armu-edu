"""
Background jobs — runs inside the Flask process via APScheduler.

Jobs:
  deadline_reminders  — every hour: notify students 24 h before due date
  weekly_digest       — Monday 08:00: AI weekly summary notification per student
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import logging

log = logging.getLogger(__name__)
_scheduler = None


def init_scheduler(app, socketio):
    global _scheduler
    if _scheduler:
        return

    _scheduler = BackgroundScheduler(timezone="UTC", daemon=True)

    _scheduler.add_job(
        func=lambda: _deadline_reminders(app, socketio),
        trigger=IntervalTrigger(hours=1),
        id="deadline_reminders",
        next_run_time=__import__("datetime").datetime.utcnow(),  # run once on startup
    )

    _scheduler.add_job(
        func=lambda: _weekly_digest(app, socketio),
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0, timezone="UTC"),
        id="weekly_digest",
    )

    _scheduler.start()
    log.info("[scheduler] started")


# ── Job implementations ───────────────────────────────────────────────────────

def _deadline_reminders(app, socketio):
    from datetime import datetime, timezone, timedelta
    from models import db
    from models.academic import Assignment
    from models.sent_reminder import SentReminder
    from models.school import Class
    from notifications import push_notification

    with app.app_context():
        now = datetime.now(timezone.utc)
        window_start = now
        window_end   = now + timedelta(hours=24)

        # Assignments due within next 24 hours
        upcoming = (
            Assignment.query
            .filter(
                Assignment.due_date >= window_start,
                Assignment.due_date <= window_end,
            )
            .all()
        )

        if not upcoming:
            return

        sent = 0
        for assignment in upcoming:
            subject = assignment.subject
            if not subject:
                continue
            klass = Class.query.get(subject.class_id)
            if not klass:
                continue

            hours_left = int((assignment.due_date.replace(tzinfo=timezone.utc) - now).total_seconds() / 3600)
            due_str = f"in {hours_left}h" if hours_left > 0 else "today"

            for student in klass.students:
                already = SentReminder.query.filter_by(
                    user_id=student.id, assignment_id=assignment.id
                ).first()
                if already:
                    continue

                type_label = {"homework": "Homework", "test": "Test", "project": "Project"}.get(
                    assignment.type, assignment.type.capitalize()
                )
                title = f"{type_label} due {due_str}"
                body  = f"{assignment.title} · {subject.name}"
                link  = "/homework" if assignment.type == "homework" else "/tests"

                push_notification(app, socketio, student.id,
                                  title=title, body=body,
                                  type="deadline", link=link)

                db.session.add(SentReminder(user_id=student.id, assignment_id=assignment.id))
                sent += 1

        if sent:
            db.session.commit()
            log.info(f"[scheduler] deadline_reminders: sent {sent} notification(s)")


def _weekly_digest(app, socketio):
    from datetime import datetime, timezone, timedelta
    from models import db
    from models.academic import Assignment, Grade
    from models.user import User
    from notifications import push_notification
    import ai as ollama
    import json

    with app.app_context():
        students = User.query.filter_by(role="student").all()
        now = datetime.now(timezone.utc)
        week_end = now + timedelta(days=7)

        for student in students:
            try:
                from models.school import Class
                klass = Class.query.get(student.class_id) if student.class_id else None
                subject_ids = [s.id for s in klass.subjects] if klass else []

                assignments = (
                    Assignment.query
                    .filter(
                        Assignment.subject_id.in_(subject_ids),
                        Assignment.due_date >= now,
                        Assignment.due_date <= week_end,
                    )
                    .order_by(Assignment.due_date)
                    .all()
                ) if subject_ids else []

                grades = (
                    Grade.query
                    .filter_by(student_id=student.id)
                    .order_by(Grade.created_at.desc())
                    .limit(5)
                    .all()
                )

                def fmt_a(a):
                    days = (a.due_date.replace(tzinfo=timezone.utc) - now).days
                    return f"- {a.title} ({a.type}, in {days}d)"

                def fmt_g(g):
                    a = Assignment.query.get(g.assignment_id)
                    subj = a.subject.name if a and a.subject else "?"
                    return f"- {subj}: {g.score}/10"

                hw_lines = "\n".join(fmt_a(a) for a in assignments) or "Nothing due this week."
                grade_lines = "\n".join(fmt_g(g) for g in grades) or "No recent grades."

                prompt = (
                    f"Write a brief, encouraging weekly summary (2 sentences) for {student.name}. "
                    f"Mention the most important thing due this week and one strength or area to improve "
                    f"based on their grades. Be specific. No bullet points.\n\n"
                    f"This week's assignments:\n{hw_lines}\n\n"
                    f"Recent grades:\n{grade_lines}"
                )

                resp = ollama.chat(
                    model=app.config["OLLAMA_TRACKER_MODEL"],
                    messages=[{"role": "user", "content": prompt}],
                    stream=False,
                )
                content = resp.json().get("message", {}).get("content", "").strip()

                if content:
                    push_notification(
                        app, socketio, student.id,
                        title="Your weekly study summary is ready",
                        body=content[:200],
                        type="study",
                        link="/dashboard",
                    )

            except Exception as e:
                log.error(f"[scheduler] weekly_digest for user {student.id}: {e}")

        log.info(f"[scheduler] weekly_digest: processed {len(students)} student(s)")
