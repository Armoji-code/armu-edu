from flask import request, jsonify
from api import blueprint
from auth import login_required
from models import db
from models.nav_config import NavConfig

# Default nav configs — seeded on first GET if no DB record exists
_DEFAULTS = {
    "student": [
        {"label": "Learn", "items": [
            {"label": "Dashboard",   "icon": "ic-dashboard",  "path": "/dashboard"},
            {"label": "Calendar",    "icon": "ic-calendar",   "path": "/calendar"},
            {"label": "Assignments", "icon": "ic-homework",   "path": "/homework"},
            {"label": "Schedule",    "icon": "ic-schedule",   "path": "/schedule"},
            {"label": "Grades",      "icon": "ic-grades",     "path": "/grades"},
        ]},
        {"label": "Engage", "items": [
            {"label": "Leaderboard", "icon": "ic-leaderboard","path": "/leaderboard"},
            {"label": "Conduct",     "icon": "ic-flag",       "path": "/conduct"},
            {"label": "Activities",  "icon": "ic-activities", "path": "/activities"},
            {"label": "Groups",      "icon": "ic-groups",     "path": "/groups"},
            {"label": "Library",     "icon": "ic-library",    "path": "/library"},
            {"label": "AI Tutor",    "icon": "ic-tutor",      "path": "/tutor"},
        ]},
        {"label": "Tools", "items": [
            {"label": "Whiteboard",  "icon": "ic-whiteboard", "path": "/whiteboard"},
            {"label": "Meeting",     "icon": "ic-meeting",    "path": "/meeting"},
            {"label": "Messages",    "icon": "ic-messages",   "path": "/messages"},
            {"label": "Settings",    "icon": "ic-settings",   "path": "/settings"},
        ]},
    ],
    "teacher": [
        {"label": "Manage", "items": [
            {"label": "Overview",    "icon": "ic-dashboard",  "path": "/dashboard"},
            {"label": "Classes",     "icon": "ic-groups",     "path": "/classes"},
            {"label": "Assignments", "icon": "ic-homework",   "path": "/assignments"},
            {"label": "Analytics",   "icon": "ic-chart",      "path": "/analytics"},
            {"label": "Schedule",    "icon": "ic-schedule",   "path": "/schedule"},
        ]},
        {"label": "Insights", "items": [
            {"label": "Conduct Log", "icon": "ic-flag",       "path": "/conduct"},
        ]},
        {"label": "Tools", "items": [
            {"label": "Whiteboard",  "icon": "ic-whiteboard", "path": "/whiteboard"},
            {"label": "Meeting",     "icon": "ic-meeting",    "path": "/meeting"},
            {"label": "Messages",    "icon": "ic-messages",   "path": "/messages"},
            {"label": "Settings",    "icon": "ic-settings",   "path": "/settings"},
        ]},
    ],
    "librarian": [
        {"label": "Library", "items": [
            {"label": "Dashboard",   "icon": "ic-dashboard",  "path": "/dashboard"},
            {"label": "Books",       "icon": "ic-library",    "path": "/books"},
            {"label": "Loans",       "icon": "ic-calendar",   "path": "/loans"},
        ]},
        {"label": "Tools", "items": [
            {"label": "Messages",    "icon": "ic-messages",   "path": "/messages"},
            {"label": "Settings",    "icon": "ic-settings",   "path": "/settings"},
        ]},
    ],
    "admin": [
        {"label": "Admin", "items": [
            {"label": "Overview",    "icon": "ic-dashboard",  "path": "/admin/dashboard"},
            {"label": "Users",       "icon": "ic-groups",     "path": "/admin/users"},
            {"label": "School",      "icon": "ic-schedule",   "path": "/admin/school"},
            {"label": "Performance", "icon": "ic-chart",      "path": "/admin/performance"},
            {"label": "Settings",    "icon": "ic-settings",   "path": "/admin/settings"},
            {"label": "Navigation",  "icon": "ic-menu",       "path": "/admin/nav"},
            {"label": "Terminal",    "icon": "ic-computer",   "path": "/admin/terminal"},
        ]},
    ],
}


@blueprint.route("/nav/config", methods=["GET"])
@login_required()
def get_nav_config(user):
    role = request.args.get("role") or user.role
    # Only admins can fetch other roles' config
    if role != user.role and user.role != "admin":
        role = user.role
    cfg = NavConfig.query.filter_by(role=role).first()
    if cfg:
        return jsonify(cfg.sections)
    return jsonify(_DEFAULTS.get(role, []))


@blueprint.route("/nav/config", methods=["PUT"])
@login_required(roles=["admin"])
def update_nav_config(user):
    data = request.get_json(force=True)
    role = data.get("role")
    sections = data.get("sections")
    if not role or sections is None:
        return jsonify({"error": "role and sections required"}), 400
    cfg = NavConfig.query.filter_by(role=role).first()
    if cfg:
        cfg.sections = sections
    else:
        cfg = NavConfig(role=role, sections=sections)
        db.session.add(cfg)
    db.session.commit()
    return jsonify({"ok": True})


@blueprint.route("/nav/config/reset", methods=["POST"])
@login_required(roles=["admin"])
def reset_nav_config(user):
    data = request.get_json(force=True)
    role = data.get("role")
    if not role:
        return jsonify({"error": "role required"}), 400
    NavConfig.query.filter_by(role=role).delete()
    db.session.commit()
    return jsonify({"ok": True, "sections": _DEFAULTS.get(role, [])})


@blueprint.route("/nav/icons", methods=["GET"])
@login_required(roles=["admin"])
def list_icons(user):
    """Returns all available icon IDs for the nav editor."""
    icons = [
        "ic-dashboard", "ic-calendar", "ic-homework", "ic-tests",
        "ic-schedule", "ic-grades", "ic-leaderboard", "ic-flag",
        "ic-activities", "ic-groups", "ic-library", "ic-tutor",
        "ic-whiteboard", "ic-meeting", "ic-messages", "ic-settings",
        "ic-chart", "ic-menu", "ic-pen", "ic-logout", "ic-moon",
        "ic-sun", "ic-plus", "ic-trash", "ic-copy", "ic-download",
    ]
    return jsonify(icons)
