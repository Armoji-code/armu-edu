from flask import request, jsonify, Response, stream_with_context, current_app
from api import blueprint
from auth import login_required
from models import db
from models.ai_session import AISession, AIMessage
import ai as ollama
import json

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
    if not user_content:
        return jsonify({"error": "message required"}), 400

    user_msg = AIMessage(session_id=session_id, role="user", content=user_content)
    db.session.add(user_msg)
    db.session.commit()

    if ai_session.model_tier == "advanced":
        model = current_app.config["OLLAMA_ADVANCED_MODEL"]
    else:
        model = current_app.config["OLLAMA_TUTOR_MODEL"]

    history = [{"role": m.role, "content": m.content} for m in ai_session.messages]

    def generate():
        full_response = []
        resp = ollama.chat(model=model, messages=history, stream=True)
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
                assistant_msg = AIMessage(
                    session_id=session_id,
                    role="assistant",
                    content="".join(full_response),
                )
                db.session.add(assistant_msg)
                db.session.commit()

    return Response(stream_with_context(generate()), content_type="text/plain")
