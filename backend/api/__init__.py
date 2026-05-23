from flask import Blueprint, jsonify

blueprint = Blueprint("api", __name__)


def err(msg, code=400):
    return jsonify({"error": msg}), code


def ok(**extra):
    return jsonify({"ok": True, **extra})

from api import auth, dashboard, homework, tests, schedule, grades, conduct, library, messages, ai, leaderboard, activities, groups, notifications, teacher, admin, librarian, meeting, nav, update, push
