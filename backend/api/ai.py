from flask import request, jsonify, Response, stream_with_context, current_app
from api import blueprint
from auth import login_required
from models import db
from models.ai_session import AISession, AIMessage
from models.social import Group
from models.daily_digest import DailyDigest
from models.academic import Assignment, Grade
import ai as _ai
import json
import io
import threading
from datetime import date, datetime, timezone


TUTOR_SYSTEM_PROMPT = """\
You are a strict but friendly AI tutor for school students. \
Your job is to make students genuinely understand — not just feel good.

Rules you must ALWAYS follow:

1. NEVER write out the solution or reveal any intermediate or final answers yourself. \
Do NOT show numbered solution steps. Do NOT say "so the answer is X" or "this equals Y". \
The student must discover every value — including intermediate results — on their own.

2. When a student asks to solve a problem, identify the first step and ask ONLY that. \
Wait for their answer before moving on. One step at a time.
   WRONG: "First do 3+4=7, then multiply by 2 to get 14, so the answer is 9."
   RIGHT: "Let's start with the parentheses. What is 3+4?"

3. When the student gives a numerical answer, compute the correct value yourself first. \
If their number is wrong, say so clearly and ask them to try again — do not move forward. \
Example: student says 8 for 3+4 → "Not quite. Count 3 and then 4 more. What do you get?"

4. NEVER say "correct", "right", or praise a wrong answer. Praising a wrong answer is a \
serious failure.

5. Only confirm and praise when the student's answer is actually correct. Then give the \
next step as a question.

6. Keep every reply short — one concept or one question at a time.

7. If a question is outside school subjects, politely redirect.

You cover all school subjects: math, science, history, literature, languages, and more.\
"""

TUTOR_SYSTEM_PROMPT_GROUP = TUTOR_SYSTEM_PROMPT + """

This is a group study session. Multiple students may be messaging. \
Each message is prefixed with [Name]: so you know who is speaking. \
Address students by name when helpful.\
"""


def _can_access(user, ai_session):
    if ai_session.user_id == user.id:
        return True
    if ai_session.group_id:
        g = Group.query.get(ai_session.group_id)
        return g is not None and user in g.members
    return False


@blueprint.route("/ai/extract", methods=["POST"])
@login_required()
def extract_file(user):
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "no file"}), 400
    filename = f.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    try:
        if ext == "pdf":
            from pdfminer.high_level import extract_text
            text = extract_text(io.BytesIO(f.read()))
        elif ext == "docx":
            from docx import Document
            doc = Document(io.BytesIO(f.read()))
            text = "\n".join(p.text for p in doc.paragraphs)
        else:
            return jsonify({"error": "unsupported file type"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"text": text, "filename": filename})


@blueprint.route("/ai/sessions", methods=["GET"])
@login_required()
def list_sessions(user):
    sessions = (
        AISession.query
        .filter_by(user_id=user.id, group_id=None)
        .order_by(AISession.created_at.desc())
        .all()
    )
    return jsonify([s.to_dict() for s in sessions])

@blueprint.route("/ai/sessions", methods=["POST"])
@login_required()
def create_session(user):
    data = request.get_json(silent=True) or {}
    session = AISession(
        user_id=user.id,
        group_id=data.get("group_id"),
        model_tier=data.get("model_tier", "standard"),
    )
    db.session.add(session)
    db.session.commit()
    return jsonify(session.to_dict()), 201

@blueprint.route("/ai/models", methods=["GET"])
@login_required()
def get_models(user):
    cfg = _ai.get_ai_config()
    return jsonify({
        "standard": cfg["tutor_model"],
        "advanced": cfg["advanced_model"],
        "provider": cfg["provider"],
    })

@blueprint.route("/ai/sessions/<int:session_id>", methods=["GET"])
@login_required()
def get_session(user, session_id):
    ai_session = AISession.query.get_or_404(session_id)
    if not _can_access(user, ai_session):
        return jsonify({"error": "forbidden"}), 403
    return jsonify(ai_session.to_dict())

@blueprint.route("/ai/sessions/<int:session_id>", methods=["PATCH"])
@login_required()
def update_session(user, session_id):
    ai_session = AISession.query.get_or_404(session_id)
    if ai_session.user_id != user.id:
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json(silent=True) or {}
    if "model_tier" in data and data["model_tier"] in ("standard", "advanced"):
        ai_session.model_tier = data["model_tier"]
    db.session.commit()
    return jsonify(ai_session.to_dict())

@blueprint.route("/ai/sessions/<int:session_id>", methods=["DELETE"])
@login_required()
def delete_session(user, session_id):
    ai_session = AISession.query.get_or_404(session_id)
    if ai_session.user_id != user.id:
        return jsonify({"error": "forbidden"}), 403
    AIMessage.query.filter_by(session_id=session_id).delete()
    db.session.delete(ai_session)
    db.session.commit()
    return jsonify({"ok": True})

@blueprint.route("/ai/sessions/<int:session_id>/messages", methods=["GET"])
@login_required()
def get_messages(user, session_id):
    ai_session = AISession.query.get_or_404(session_id)
    if not _can_access(user, ai_session):
        return jsonify({"error": "forbidden"}), 403
    return jsonify([m.to_dict() for m in ai_session.messages])

@blueprint.route("/ai/sessions/<int:session_id>/chat", methods=["POST"])
@login_required()
def chat(user, session_id):
    ai_session = AISession.query.get_or_404(session_id)
    if not _can_access(user, ai_session):
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    user_content = data.get("message", "").strip()
    image_b64 = data.get("image")
    if not user_content and not image_b64:
        return jsonify({"error": "message required"}), 400

    is_group = ai_session.group_id is not None
    core = user_content or "(image)"
    stored_content = f"[{user.name}]: {core}" if is_group else core

    user_msg = AIMessage(
        session_id=session_id,
        role="user",
        content=stored_content,
        sender_id=user.id,
    )
    db.session.add(user_msg)
    db.session.commit()

    ai_cfg = _ai.get_ai_config()
    model = ai_cfg["advanced_model"] if ai_session.model_tier == "advanced" else ai_cfg["tutor_model"]
    temperature = ai_cfg["tutor_temperature"]
    top_p = ai_cfg["tutor_top_p"]
    max_tokens = ai_cfg["max_tokens"]

    custom_prompt = ai_cfg["tutor_system_prompt"].strip()
    base_prompt = TUTOR_SYSTEM_PROMPT_GROUP if is_group else TUTOR_SYSTEM_PROMPT
    system_prompt = custom_prompt if custom_prompt else base_prompt

    all_msgs = AIMessage.query.filter_by(session_id=session_id).order_by(AIMessage.created_at).all()
    history = [{"role": "system", "content": system_prompt}] + \
              [{"role": m.role, "content": m.content} for m in all_msgs]
    images = [image_b64] if image_b64 else None
    app = current_app._get_current_object()

    def generate():
        full_response = []
        try:
            for token in _ai.stream(model=model, messages=history, temperature=temperature,
                                    top_p=top_p, max_tokens=max_tokens, images=images):
                full_response.append(token)
                yield token
        except Exception as e:
            yield f"\n\n[Error: {e}]"
        finally:
            if full_response:
                with app.app_context():
                    assistant_msg = AIMessage(
                        session_id=session_id,
                        role="assistant",
                        content="".join(full_response),
                    )
                    db.session.add(assistant_msg)
                    db.session.commit()

                    if not is_group:
                        msg_count = AIMessage.query.filter_by(session_id=session_id).count()
                        if msg_count == 2:
                            t = threading.Thread(
                                target=_auto_title,
                                args=(app, session_id,
                                      ai_cfg["tracker_model"],
                                      ai_cfg["tracker_temperature"],
                                      user_content or "image",
                                      "".join(full_response)),
                                daemon=True,
                            )
                            t.start()

    return Response(stream_with_context(generate()), content_type="text/plain")


# ── Group AI sessions ────────────────────────────────────────────────────────

@blueprint.route("/groups/<int:group_id>/ai/session", methods=["GET"])
@login_required()
def group_ai_session(user, group_id):
    g = Group.query.get_or_404(group_id)
    if user not in g.members:
        return jsonify({"error": "forbidden"}), 403

    session = (
        AISession.query
        .filter_by(group_id=group_id)
        .order_by(AISession.created_at.desc())
        .first()
    )
    if not session:
        session = AISession(
            user_id=user.id,
            group_id=group_id,
            title=f"{g.name}",
            model_tier="standard",
        )
        db.session.add(session)
        db.session.commit()

    return jsonify(session.to_dict())


@blueprint.route("/ai/tutor-nudge", methods=["GET"])
@login_required()
def tutor_nudge(user):
    from models.school import Class
    from datetime import timedelta

    klass = Class.query.get(user.class_id) if user.class_id else None
    subject_ids = [s.id for s in klass.subjects] if klass else []
    now = datetime.now(timezone.utc)

    upcoming = (
        Assignment.query
        .filter(
            Assignment.subject_id.in_(subject_ids),
            Assignment.due_date >= now,
            Assignment.due_date <= now + timedelta(days=7),
        )
        .order_by(Assignment.due_date)
        .limit(5)
        .all()
    ) if subject_ids else []

    if upcoming:
        lines = []
        for a in upcoming:
            days = max(0, (a.due_date.replace(tzinfo=timezone.utc) - now).days)
            due = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
            lines.append(f"- {a.title} ({a.type}, {a.subject.name}, due {due})")
        context = "Upcoming assignments:\n" + "\n".join(lines)
    else:
        context = "No upcoming assignments found."

    prompt = (
        f"You are generating study suggestions for {user.name}, a school student.\n"
        f"{context}\n\n"
        f"Return a JSON array of exactly 3 study suggestions. "
        f"Each item must have: \"label\" (3-5 words, the chip text shown to the student) "
        f"and \"message\" (one sentence the student will send to the AI tutor to start studying). "
        f"Base suggestions on the actual assignments above. "
        f"Example format: "
        f'[{{"label":"Review quadratic equations","message":"Can you help me review quadratic equations for my math test tomorrow?"}}]'
        f"\nReturn only the JSON array, nothing else."
    )

    try:
        ai_cfg = _ai.get_ai_config()
        raw = _ai.complete(model=ai_cfg["tracker_model"],
                           messages=[{"role": "user", "content": prompt}],
                           temperature=ai_cfg["tracker_temperature"]).strip()
        start = raw.find("[")
        end = raw.rfind("]") + 1
        nudges = json.loads(raw[start:end]) if start != -1 else []
        nudges = [n for n in nudges if isinstance(n, dict) and "label" in n and "message" in n][:3]
    except Exception:
        nudges = []

    if not nudges:
        nudges = [
            {"label": "Explain a concept", "message": "Can you explain a concept I'm struggling with?"},
            {"label": "Quiz me on anything", "message": "Can you quiz me on something from my recent schoolwork?"},
        ]

    return jsonify({"nudges": nudges})


@blueprint.route("/ai/daily-digest", methods=["GET"])
@login_required()
def daily_digest(user):
    today = date.today()
    force = request.args.get("force") == "1"

    if not force:
        cached = DailyDigest.query.filter_by(user_id=user.id, date=today).first()
        if cached:
            return jsonify(cached.to_dict())

    # Build context from upcoming assignments and recent grades
    from models.school import Class
    from sqlalchemy import and_
    klass = Class.query.get(user.class_id) if user.class_id else None
    subject_ids = [s.id for s in klass.subjects] if klass else []

    now = datetime.now(timezone.utc)
    week_out = datetime(now.year, now.month, now.day + 7 if now.day + 7 <= 28 else 28,
                        tzinfo=timezone.utc)

    assignments = (
        Assignment.query
        .filter(
            Assignment.subject_id.in_(subject_ids),
            Assignment.due_date >= now,
        )
        .order_by(Assignment.due_date)
        .limit(10)
        .all()
    ) if subject_ids else []

    grades = (
        Grade.query
        .filter_by(student_id=user.id)
        .order_by(Grade.created_at.desc())
        .limit(10)
        .all()
    )

    def fmt_assignment(a):
        days = (a.due_date.replace(tzinfo=timezone.utc) - now).days
        due = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
        return f"- {a.title} ({a.type}, due {due})"

    def fmt_grade(g):
        a = Assignment.query.get(g.assignment_id)
        subj = a.subject.name if a and a.subject else "unknown"
        return f"- {subj}: {g.score}/10"

    hw_lines = "\n".join(fmt_assignment(a) for a in assignments) or "No upcoming assignments."
    grade_lines = "\n".join(fmt_grade(g) for g in grades) or "No recent grades."

    prompt = (
        f"You are a school advisor. Write a short, personal, encouraging message (2-3 sentences) "
        f"for {user.name} based on their upcoming work and recent grades. "
        f"Tell them what to focus on most urgently today and why. Be specific, use the assignment names. "
        f"Do not use bullet points or headers. Plain prose only.\n\n"
        f"Upcoming assignments:\n{hw_lines}\n\n"
        f"Recent grades:\n{grade_lines}"
    )

    ai_cfg = _ai.get_ai_config()
    model = ai_cfg["tracker_model"]
    tracker_temp = ai_cfg["tracker_temperature"]
    app = current_app._get_current_object()

    def generate():
        full = []
        try:
            for token in _ai.stream(model=model, messages=[{"role": "user", "content": prompt}],
                                    temperature=tracker_temp):
                full.append(token)
                yield token
        except Exception as e:
            yield f"[Error: {e}]"
        finally:
            content = "".join(full).strip()
            if content:
                with app.app_context():
                    existing = DailyDigest.query.filter_by(user_id=user.id, date=today).first()
                    if existing:
                        existing.content = content
                        existing.generated_at = datetime.now(timezone.utc)
                    else:
                        db.session.add(DailyDigest(
                            user_id=user.id, date=today, content=content
                        ))
                    db.session.commit()

    return Response(stream_with_context(generate()), content_type="text/plain")


@blueprint.route("/ai/teacher-digest", methods=["GET"])
@login_required(roles=["teacher"])
def teacher_digest(user):
    from models.school import Subject
    from datetime import timedelta

    today = date.today()
    force = request.args.get("force") == "1"

    if not force:
        cached = DailyDigest.query.filter_by(user_id=user.id, date=today).first()
        if cached:
            return jsonify(cached.to_dict())

    subjects = Subject.query.filter_by(teacher_id=user.id).all()
    subject_ids = [s.id for s in subjects]
    now = datetime.now(timezone.utc)

    all_assignments = Assignment.query.filter(
        Assignment.subject_id.in_(subject_ids)
    ).all() if subject_ids else []

    ungraded_lines = []
    for a in all_assignments:
        class_size = len(a.subject.klass.students)
        graded = Grade.query.filter_by(assignment_id=a.id).count()
        if graded < class_size:
            days_ago = (now - a.due_date.replace(tzinfo=timezone.utc)).days
            when = f"{days_ago}d overdue" if days_ago > 0 else "due soon"
            ungraded_lines.append(
                f"- {a.title} ({a.subject.name}): {graded}/{class_size} graded, {when}"
            )

    upcoming = Assignment.query.filter(
        Assignment.subject_id.in_(subject_ids),
        Assignment.due_date >= now,
        Assignment.due_date <= now + timedelta(days=7),
    ).order_by(Assignment.due_date).limit(5).all() if subject_ids else []

    recent_grades = (
        Grade.query.join(Assignment)
        .filter(Assignment.subject_id.in_(subject_ids))
        .order_by(Grade.created_at.desc())
        .limit(20).all()
    ) if subject_ids else []
    avg = round(sum(g.score for g in recent_grades) / len(recent_grades), 1) if recent_grades else None

    parts = []
    if ungraded_lines:
        parts.append("Needs grading:\n" + "\n".join(ungraded_lines[:5]))
    if upcoming:
        parts.append("Upcoming deadlines:\n" + "\n".join(
            f"- {a.title} ({a.subject.name}, "
            f"in {max(0,(a.due_date.replace(tzinfo=timezone.utc)-now).days)}d)"
            for a in upcoming
        ))
    if avg is not None:
        parts.append(f"Recent class average: {avg}/100")

    context = "\n\n".join(parts) or "No pending tasks."

    prompt = (
        f"You are a school management assistant. Write a short daily briefing (2-3 sentences) "
        f"for teacher {user.name}. Focus on what needs attention today — ungraded work, "
        f"upcoming deadlines, class performance. Be specific and direct. Plain prose only.\n\n"
        f"{context}"
    )

    ai_cfg = _ai.get_ai_config()
    model = ai_cfg["tracker_model"]
    tracker_temp = ai_cfg["tracker_temperature"]
    app = current_app._get_current_object()

    def generate():
        full = []
        try:
            for token in _ai.stream(model=model, messages=[{"role": "user", "content": prompt}],
                                    temperature=tracker_temp):
                full.append(token)
                yield token
        except Exception as e:
            yield f"[Error: {e}]"
        finally:
            content = "".join(full).strip()
            if content:
                with app.app_context():
                    existing = DailyDigest.query.filter_by(user_id=user.id, date=today).first()
                    if existing:
                        existing.content = content
                        existing.generated_at = datetime.now(timezone.utc)
                    else:
                        db.session.add(DailyDigest(user_id=user.id, date=today, content=content))
                    db.session.commit()

    return Response(stream_with_context(generate()), content_type="text/plain")


@blueprint.route("/ai/teacher-nudge", methods=["GET"])
@login_required(roles=["teacher"])
def teacher_nudge(user):
    from models.school import Subject
    from datetime import timedelta

    subjects = Subject.query.filter_by(teacher_id=user.id).all()
    subject_ids = [s.id for s in subjects]
    now = datetime.now(timezone.utc)

    task_lines = []
    all_assignments = Assignment.query.filter(
        Assignment.subject_id.in_(subject_ids)
    ).all() if subject_ids else []

    for a in all_assignments:
        class_size = len(a.subject.klass.students)
        graded = Grade.query.filter_by(assignment_id=a.id).count()
        if graded < class_size:
            missing = class_size - graded
            days_ago = (now - a.due_date.replace(tzinfo=timezone.utc)).days
            status = f"{days_ago}d overdue" if days_ago > 0 else "due soon"
            task_lines.append(
                f"- {a.title} ({a.subject.name}): {missing} student(s) ungraded, {status}"
            )

    upcoming = Assignment.query.filter(
        Assignment.subject_id.in_(subject_ids),
        Assignment.due_date >= now,
        Assignment.due_date <= now + timedelta(days=7),
    ).limit(3).all() if subject_ids else []

    for a in upcoming:
        days = max(0, (a.due_date.replace(tzinfo=timezone.utc) - now).days)
        task_lines.append(f"- {a.title} ({a.subject.name}) due in {days} days")

    context = "\n".join(task_lines[:8]) if task_lines else "All caught up."

    prompt = (
        f"You are generating action chips for teacher {user.name}.\n"
        f"Current tasks:\n{context}\n\n"
        f"Return a JSON array of exactly 3 short action chips. "
        f"Each item: \"label\" (3-6 words, starts with a verb) and "
        f"\"href\" (one of: \"/assignments\", \"/classes\", \"/dashboard\"). "
        f"Base on the actual tasks above. "
        f'Example: [{{"label":"Grade Physics test","href":"/assignments"}}]\n'
        f"Return only the JSON array, nothing else."
    )

    try:
        ai_cfg = _ai.get_ai_config()
        raw = _ai.complete(model=ai_cfg["tracker_model"],
                           messages=[{"role": "user", "content": prompt}],
                           temperature=ai_cfg["tracker_temperature"]).strip()
        start, end = raw.find("["), raw.rfind("]") + 1
        nudges = json.loads(raw[start:end]) if start != -1 else []
        nudges = [n for n in nudges if isinstance(n, dict) and "label" in n and "href" in n][:3]
    except Exception:
        nudges = []

    if not nudges:
        nudges = [
            {"label": "Review ungraded work", "href": "/assignments"},
            {"label": "Check class roster",   "href": "/classes"},
        ]

    return jsonify({"nudges": nudges})


def _auto_title(app, session_id, model, temperature, user_msg, ai_msg):
    with app.app_context():
        try:
            prompt = (
                "Write a short title (3–6 words, no quotes, no trailing punctuation) "
                "that summarises this conversation.\n\n"
                f"User: {user_msg[:300]}\nAssistant: {ai_msg[:300]}"
            )
            title = _ai.complete(model=model,
                                 messages=[{"role": "user", "content": prompt}],
                                 temperature=temperature).strip().strip('"').strip("'")[:80]
            if title:
                s = AISession.query.get(session_id)
                if s:
                    s.title = title
                    db.session.commit()
        except Exception as e:
            print(f"[auto-title] error: {e}")
