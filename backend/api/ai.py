from flask import request, jsonify, Response, stream_with_context, current_app
from api import blueprint
from auth import login_required
from models import db
from models.ai_session import AISession, AIMessage
from models.social import Group
import ai as ollama
import json
import io
import threading


TUTOR_SYSTEM_PROMPT = """\
You are a Socratic AI tutor for school students. Your single most important rule: \
never give the answer directly, no matter how much the student asks.

Instead, guide them to discover it themselves:
- Ask one focused question that points them toward the next step
- Name the concept or formula they should think about, without applying it for them
- If they're on the right track, confirm it briefly and ask what comes next
- If they're stuck after a hint, give a slightly more specific nudge — still not the answer
- When they reach the correct answer on their own, affirm it clearly

Keep replies short. One nudge at a time. Be warm but firm — if they demand the answer, \
explain that working it out themselves is the whole point.\
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

@blueprint.route("/ai/sessions/<int:session_id>", methods=["GET"])
@login_required()
def get_session(user, session_id):
    ai_session = AISession.query.get_or_404(session_id)
    if not _can_access(user, ai_session):
        return jsonify({"error": "forbidden"}), 403
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

    # Save the user message immediately with placeholder content;
    # if an image was attached we update it after stage-1 description.
    core_placeholder = user_content or "(image)"
    stored_placeholder = f"[{user.name}]: {core_placeholder}" if is_group else core_placeholder
    user_msg = AIMessage(
        session_id=session_id,
        role="user",
        content=stored_placeholder,
        sender_id=user.id,
    )
    db.session.add(user_msg)
    db.session.commit()

    if ai_session.model_tier == "advanced":
        text_model = current_app.config["OLLAMA_ADVANCED_MODEL"]
    else:
        text_model = current_app.config["OLLAMA_TEXT_MODEL"]
    vision_model = current_app.config["OLLAMA_VISION_MODEL"]
    system_prompt = TUTOR_SYSTEM_PROMPT_GROUP if is_group else TUTOR_SYSTEM_PROMPT
    app = current_app._get_current_object()

    def generate():
        full_response = []
        try:
            # ── Stage 1: describe image (runs inside generator so we can stream status) ──
            if image_b64:
                yield "_Analyzing image…_\n\n"
                try:
                    desc_resp = ollama.chat(
                        model=vision_model,
                        messages=[{"role": "user", "content": (
                            "Describe this image in full detail. "
                            "If it contains text, equations, math problems, diagrams, or charts, "
                            "transcribe and explain them exactly."
                        )}],
                        stream=False,
                        images=[image_b64],
                    )
                    description = desc_resp.json().get("message", {}).get("content", "").strip()
                except Exception as e:
                    description = f"(image could not be processed: {e})"

                core = f"[Image description: {description}]"
                if user_content:
                    core = f"{core}\n\n{user_content}"
                stored_content = f"[{user.name}]: {core}" if is_group else core
                with app.app_context():
                    msg = AIMessage.query.get(user_msg.id)
                    if msg:
                        msg.content = stored_content
                        db.session.commit()

            # ── Stage 2: build history and stream from text model ──────────────────────
            with app.app_context():
                all_msgs = AIMessage.query.filter_by(session_id=session_id).order_by(AIMessage.created_at).all()
                history = [{"role": "system", "content": system_prompt}] + \
                          [{"role": m.role, "content": m.content} for m in all_msgs]

            resp = ollama.chat(model=text_model, messages=history, stream=True)
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = chunk.get("message", {}).get("content", "")
                if token:
                    full_response.append(token)
                    yield token
                if chunk.get("done"):
                    break
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
                                      app.config["OLLAMA_TRACKER_MODEL"],
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


def _auto_title(app, session_id, model, user_msg, ai_msg):
    with app.app_context():
        try:
            prompt = (
                "Write a short title (3–6 words, no quotes, no trailing punctuation) "
                "that summarises this conversation.\n\n"
                f"User: {user_msg[:300]}\nAssistant: {ai_msg[:300]}"
            )
            resp = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
            title = resp.json().get("message", {}).get("content", "").strip().strip('"').strip("'")[:80]
            if title:
                s = AISession.query.get(session_id)
                if s:
                    s.title = title
                    db.session.commit()
        except Exception as e:
            print(f"[auto-title] error: {e}")
