import os
import psutil
import requests as _requests
from flask import request, jsonify, current_app
from api import blueprint
from auth import login_required
from models import db
from models.user import User
from models.school import School, Class, Subject
from models.academic import Assignment, Grade


def _school(user):
    return School.query.get(user.school_id)


# ── Admin: performance ────────────────────────────────────────────────────────

@blueprint.route("/admin/performance", methods=["GET"])
@login_required(roles=["admin"])
def admin_performance(user):
    # CPU
    cpu_pct      = psutil.cpu_percent(interval=None)
    cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
    cpu_cores    = psutil.cpu_count(logical=True)
    cpu_freq     = psutil.cpu_freq()

    # RAM
    ram = psutil.virtual_memory()

    # Disk (root mount)
    disk = psutil.disk_usage("/")

    # Flask process memory
    proc = psutil.Process(os.getpid())
    proc_mem_mb = round(proc.memory_info().rss / 1024 / 1024, 1)

    # Ollama — running models
    ollama_url = current_app.config.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_ok  = False
    ollama_models = []
    try:
        resp = _requests.get(f"{ollama_url}/api/ps", timeout=3)
        if resp.ok:
            ollama_ok = True
            for m in resp.json().get("models", []):
                ollama_models.append({
                    "name":       m.get("name", ""),
                    "size_gb":    round(m.get("size", 0) / 1024**3, 2),
                    "vram_gb":    round(m.get("size_vram", 0) / 1024**3, 2),
                    "expires_at": m.get("expires_at", ""),
                })
    except Exception:
        pass

    return jsonify({
        "cpu": {
            "percent":      cpu_pct,
            "per_core":     cpu_per_core,
            "cores":        cpu_cores,
            "freq_mhz":     round(cpu_freq.current, 0) if cpu_freq else None,
        },
        "ram": {
            "total_gb":  round(ram.total     / 1024**3, 2),
            "used_gb":   round(ram.used      / 1024**3, 2),
            "avail_gb":  round(ram.available / 1024**3, 2),
            "percent":   ram.percent,
        },
        "disk": {
            "total_gb": round(disk.total / 1024**3, 1),
            "used_gb":  round(disk.used  / 1024**3, 1),
            "free_gb":  round(disk.free  / 1024**3, 1),
            "percent":  disk.percent,
        },
        "process_mem_mb": proc_mem_mb,
        "ollama": {
            "reachable": ollama_ok,
            "url":       ollama_url,
            "models":    ollama_models,
        },
    })


# ── Public: tab visibility ────────────────────────────────────────────────────

@blueprint.route("/settings/tabs", methods=["GET"])
@login_required()
def settings_tabs(user):
    s = (_school(user).settings or {})
    return jsonify({"hidden": s.get("hidden_tabs", [])})


# ── Admin: overview ───────────────────────────────────────────────────────────

@blueprint.route("/admin/overview", methods=["GET"])
@login_required(roles=["admin"])
def admin_overview(user):
    school = _school(user)
    users = User.query.filter_by(school_id=school.id).all()
    role_counts = {}
    for u in users:
        role_counts[u.role] = role_counts.get(u.role, 0) + 1

    classes  = Class.query.filter_by(school_id=school.id).count()
    subjects = Subject.query.join(Class).filter(Class.school_id == school.id).count()
    assigns  = Assignment.query.join(Subject).join(Class).filter(Class.school_id == school.id).count()
    grades   = Grade.query.join(Assignment).join(Subject).join(Class).filter(Class.school_id == school.id).count()

    return jsonify({
        "school_name":  school.name,
        "users":        role_counts,
        "total_users":  len(users),
        "classes":      classes,
        "subjects":     subjects,
        "assignments":  assigns,
        "grades_given": grades,
    })


# ── Admin: settings ───────────────────────────────────────────────────────────

@blueprint.route("/admin/settings", methods=["GET"])
@login_required(roles=["admin"])
def admin_get_settings(user):
    school = _school(user)
    s = school.settings or {}
    cfg = current_app.config
    return jsonify({
        "school_name":                 school.name,
        "hidden_tabs":                 s.get("hidden_tabs", []),
        "ai_enabled":                  s.get("ai_enabled", True),
        "tutor_enabled":               s.get("tutor_enabled", True),
        "digest_enabled":              s.get("digest_enabled", True),
        "nudges_enabled":              s.get("nudges_enabled", True),
        "deadline_reminders_enabled":  s.get("deadline_reminders_enabled", True),
        "weekly_digest_enabled":       s.get("weekly_digest_enabled", True),
        # AI provider config
        "ai_provider":                 s.get("ai_provider", cfg.get("AI_PROVIDER", "ollama")),
        "ollama_base_url":             s.get("ollama_base_url", cfg.get("OLLAMA_BASE_URL", "http://localhost:11434")),
        "ai_api_key_set":              bool(s.get("ai_api_key", "")),
        "ai_api_base_url":             s.get("ai_api_base_url", ""),
        # Model names
        "tutor_model":                 s.get("tutor_model", s.get("ollama_tutor_model",
                                            cfg.get("OLLAMA_TUTOR_MODEL", "gemma3:12b"))),
        "advanced_model":              s.get("advanced_model", s.get("ollama_advanced_model",
                                            cfg.get("OLLAMA_ADVANCED_MODEL", "gemma3:12b"))),
        "tracker_model":               s.get("tracker_model", s.get("ollama_tracker_model",
                                            cfg.get("OLLAMA_TRACKER_MODEL", "llama3.2:3b"))),
        # Generation params
        "tutor_temperature":           float(s.get("tutor_temperature", 0.7)),
        "tracker_temperature":         float(s.get("tracker_temperature", 0.3)),
        "tutor_top_p":                 float(s.get("tutor_top_p", 1.0)),
        "max_tokens":                  int(s.get("max_tokens", 2048)),
        "tutor_system_prompt":         s.get("tutor_system_prompt", ""),
        # TURN server
        "turn_url":                    s.get("turn_url",      cfg.get("TURN_URL", "")),
        "turn_username":               s.get("turn_username", cfg.get("TURN_USERNAME", "")),
        "turn_credential_set":         bool(s.get("turn_credential", cfg.get("TURN_CREDENTIAL", ""))),
    })


@blueprint.route("/admin/settings", methods=["PATCH"])
@login_required(roles=["admin"])
def admin_update_settings(user):
    school = _school(user)
    data = request.get_json(silent=True) or {}
    settings = dict(school.settings or {})

    if "school_name" in data and data["school_name"].strip():
        school.name = data["school_name"].strip()
    if "hidden_tabs" in data:
        settings["hidden_tabs"] = list(data["hidden_tabs"])
    for key in ("ai_enabled", "tutor_enabled", "digest_enabled", "nudges_enabled",
                "deadline_reminders_enabled", "weekly_digest_enabled"):
        if key in data:
            settings[key] = bool(data[key])
    # Provider selection
    if "ai_provider" in data and data["ai_provider"] in ("ollama", "openai", "anthropic"):
        settings["ai_provider"] = data["ai_provider"]
    for key in ("ollama_base_url", "ai_api_base_url", "tutor_system_prompt"):
        if key in data:
            settings[key] = str(data[key]).strip()
    if "ai_api_key" in data and str(data["ai_api_key"]).strip():
        settings["ai_api_key"] = str(data["ai_api_key"]).strip()
    # Model names
    for key in ("tutor_model", "advanced_model", "tracker_model"):
        if key in data and str(data[key]).strip():
            settings[key] = str(data[key]).strip()
    # Generation params
    for key, lo, hi in (("tutor_temperature", 0.0, 2.0),
                        ("tracker_temperature", 0.0, 2.0),
                        ("tutor_top_p", 0.0, 1.0)):
        if key in data:
            try:
                settings[key] = max(lo, min(hi, float(data[key])))
            except (TypeError, ValueError):
                pass
    if "max_tokens" in data:
        try:
            settings["max_tokens"] = max(64, min(32768, int(data["max_tokens"])))
        except (TypeError, ValueError):
            pass

    # TURN server
    for key in ("turn_url", "turn_username"):
        if key in data:
            settings[key] = str(data[key]).strip()
    if "turn_credential" in data and str(data["turn_credential"]).strip():
        settings["turn_credential"] = str(data["turn_credential"]).strip()

    school.settings = settings
    db.session.commit()
    return jsonify({"ok": True})


@blueprint.route("/admin/branding", methods=["GET"])
@login_required(roles=["admin"])
def admin_get_branding(user):
    school = _school(user)
    return jsonify((school.settings or {}).get("branding", {}))


@blueprint.route("/admin/branding", methods=["PATCH"])
@login_required(roles=["admin"])
def admin_save_branding(user):
    school = _school(user)
    data = request.get_json(silent=True) or {}
    settings = dict(school.settings or {})
    branding = {}
    if "logo_data" in data:
        branding["logo_data"] = data["logo_data"]
    if "logo_fit" in data and data["logo_fit"] in ("contain", "cover", "fill"):
        branding["logo_fit"] = data["logo_fit"]
    if "logo_height" in data:
        branding["logo_height"] = max(16, min(94, int(data["logo_height"])))
    if isinstance(data.get("colors"), dict):
        allowed = ("g1","g2","g3","dark_bg","dark_bg2","dark_bg3","dark_bg4",
                   "light_bg","light_bg2","light_bg3","light_bg4")
        branding["colors"] = {k: v for k, v in data["colors"].items() if k in allowed}
    settings["branding"] = branding
    school.settings = settings
    db.session.commit()
    return jsonify({"ok": True})


@blueprint.route("/admin/ai/pull", methods=["POST"])
@login_required(roles=["admin"])
def admin_ai_pull(user):
    """Pull (install) an Ollama model. Streams progress as SSE."""
    import requests as _req
    from flask import Response, stream_with_context
    data = request.get_json(silent=True) or {}
    model = str(data.get("model", "")).strip()
    if not model:
        return jsonify({"error": "model name required"}), 400

    school = _school(user)
    s = school.settings or {}
    base_url = s.get("ollama_base_url", current_app.config.get("OLLAMA_BASE_URL", "http://localhost:11434"))

    def pull_stream():
        try:
            resp = _req.post(f"{base_url}/api/pull", json={"model": model}, stream=True, timeout=600)
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    yield f"data: {line.decode()}\n\n"
        except Exception as e:
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
        yield "data: {\"status\": \"done\"}\n\n"

    return Response(stream_with_context(pull_stream()), content_type="text/event-stream")


# ── Admin: users ──────────────────────────────────────────────────────────────

@blueprint.route("/admin/users", methods=["GET"])
@login_required(roles=["admin"])
def admin_users(user):
    school = _school(user)
    users = User.query.filter_by(school_id=school.id).order_by(User.role, User.name).all()
    return jsonify([u.to_dict() for u in users])


@blueprint.route("/admin/users", methods=["POST"])
@login_required(roles=["admin"])
def admin_create_user(user):
    school = _school(user)
    data = request.get_json(silent=True) or {}
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    role     = data.get("role", "student")
    class_id = data.get("class_id") or None

    if not name or not email or not password:
        return jsonify({"error": "name, email, and password required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already in use"}), 409

    u = User(name=name, email=email, role=role, school_id=school.id, class_id=class_id)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return jsonify(u.to_dict()), 201


@blueprint.route("/admin/users/<int:uid>", methods=["PATCH"])
@login_required(roles=["admin"])
def admin_update_user(user, uid):
    school = _school(user)
    target = User.query.filter_by(id=uid, school_id=school.id).first_or_404()
    data = request.get_json(silent=True) or {}

    if "name" in data and data["name"].strip():
        target.name = data["name"].strip()
    if "email" in data:
        new_email = data["email"].strip().lower()
        if new_email != target.email and User.query.filter_by(email=new_email).first():
            return jsonify({"error": "email already in use"}), 409
        target.email = new_email
    if "role" in data:
        target.role = data["role"]
    if "class_id" in data:
        target.class_id = data["class_id"] or None
    if "password" in data and str(data["password"]).strip():
        target.set_password(str(data["password"]).strip())
    if "can_change_password" in data:
        target.can_change_password = bool(data["can_change_password"])

    db.session.commit()
    return jsonify(target.to_dict())


@blueprint.route("/admin/users/<int:uid>", methods=["DELETE"])
@login_required(roles=["admin"])
def admin_delete_user(user, uid):
    school = _school(user)
    if uid == user.id:
        return jsonify({"error": "cannot delete yourself"}), 400
    target = User.query.filter_by(id=uid, school_id=school.id).first_or_404()
    db.session.delete(target)
    db.session.commit()
    return jsonify({"ok": True})


# ── Admin: classes ────────────────────────────────────────────────────────────

@blueprint.route("/admin/classes", methods=["GET"])
@login_required(roles=["admin"])
def admin_classes(user):
    school = _school(user)
    classes = Class.query.filter_by(school_id=school.id).order_by(Class.grade_year, Class.name).all()
    return jsonify([{
        "id":            c.id,
        "name":          c.name,
        "grade_year":    c.grade_year,
        "student_count": len(c.students),
        "subjects": [{
            "id":           s.id,
            "name":         s.name,
            "teacher_id":   s.teacher_id,
            "teacher_name": s.teacher.name,
        } for s in c.subjects],
    } for c in classes])


@blueprint.route("/admin/classes", methods=["POST"])
@login_required(roles=["admin"])
def admin_create_class(user):
    school = _school(user)
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    year = data.get("grade_year", 0)
    if not name:
        return jsonify({"error": "name required"}), 400
    c = Class(name=name, grade_year=int(year), school_id=school.id)
    db.session.add(c)
    db.session.commit()
    return jsonify({"id": c.id, "name": c.name}), 201


@blueprint.route("/admin/classes/<int:class_id>", methods=["PATCH"])
@login_required(roles=["admin"])
def admin_update_class(user, class_id):
    school = _school(user)
    c = Class.query.filter_by(id=class_id, school_id=school.id).first_or_404()
    data = request.get_json(silent=True) or {}
    if "name" in data and data["name"].strip():
        c.name = data["name"].strip()
    if "grade_year" in data:
        c.grade_year = int(data["grade_year"])
    db.session.commit()
    return jsonify({"ok": True})


@blueprint.route("/admin/classes/<int:class_id>", methods=["DELETE"])
@login_required(roles=["admin"])
def admin_delete_class(user, class_id):
    school = _school(user)
    c = Class.query.filter_by(id=class_id, school_id=school.id).first_or_404()
    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})


# ── Admin: subjects ───────────────────────────────────────────────────────────

@blueprint.route("/admin/subjects", methods=["POST"])
@login_required(roles=["admin"])
def admin_create_subject(user):
    school = _school(user)
    data = request.get_json(silent=True) or {}
    name       = data.get("name", "").strip()
    class_id   = data.get("class_id")
    teacher_id = data.get("teacher_id")
    if not name or not class_id or not teacher_id:
        return jsonify({"error": "name, class_id, teacher_id required"}), 400
    Class.query.filter_by(id=class_id, school_id=school.id).first_or_404()
    s = Subject(name=name, class_id=class_id, teacher_id=teacher_id)
    db.session.add(s)
    db.session.commit()
    return jsonify({"id": s.id, "name": s.name}), 201


@blueprint.route("/admin/subjects/<int:subject_id>", methods=["DELETE"])
@login_required(roles=["admin"])
def admin_delete_subject(user, subject_id):
    school = _school(user)
    s = Subject.query.join(Class).filter(
        Subject.id == subject_id,
        Class.school_id == school.id,
    ).first_or_404()
    db.session.delete(s)
    db.session.commit()
    return jsonify({"ok": True})
