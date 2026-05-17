from flask import request, jsonify, Response, stream_with_context, current_app
from api import blueprint
from auth import login_required
from models import db
from models.ai_session import AISession, AIMessage
import ai as ollama
import json
import io
import threading

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
        .filter_by(user_id=user.id)
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
    if ai_session.user_id != user.id:
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
    if ai_session.user_id != user.id:
        return jsonify({"error": "forbidden"}), 403
    return jsonify([m.to_dict() for m in ai_session.messages])

@blueprint.route("/ai/sessions/<int:session_id>/chat", methods=["POST"])
@login_required()
def chat(user, session_id):
    ai_session = AISession.query.get_or_404(session_id)
    if ai_session.user_id != user.id:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    user_content = data.get("message", "").strip()
    image_b64 = data.get("image")  # optional base64 string (no data URI prefix)
    if not user_content and not image_b64:
        return jsonify({"error": "message required"}), 400

    user_msg = AIMessage(session_id=session_id, role="user", content=user_content or "(image)")
    db.session.add(user_msg)
    db.session.commit()

    if ai_session.model_tier == "advanced":
        model = current_app.config["OLLAMA_ADVANCED_MODEL"]
    else:
        model = current_app.config["OLLAMA_TUTOR_MODEL"]

    history = [{"role": m.role, "content": m.content} for m in ai_session.messages]
    images = [image_b64] if image_b64 else None

    def generate():
        full_response = []
        try:
            resp = ollama.chat(model=model, messages=history, stream=True, images=images)
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
                assistant_msg = AIMessage(
                    session_id=session_id,
                    role="assistant",
                    content="".join(full_response),
                )
                db.session.add(assistant_msg)
                db.session.commit()

                # Auto-title in a background thread so the stream closes immediately
                msg_count = AIMessage.query.filter_by(session_id=session_id).count()
                if msg_count == 2:
                    app = current_app._get_current_object()
                    t = threading.Thread(
                        target=_auto_title,
                        args=(app, session_id,
                              current_app.config["OLLAMA_TRACKER_MODEL"],
                              user_content or "image",
                              "".join(full_response)),
                        daemon=True,
                    )
                    t.start()

    return Response(stream_with_context(generate()), content_type="text/plain")


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
