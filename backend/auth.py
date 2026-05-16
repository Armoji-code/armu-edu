from functools import wraps
from flask import session, jsonify
from models.user import User

def login_required(roles=None):
    """Decorator that enforces authentication and optional role restriction."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"error": "not authenticated"}), 401
            user = User.query.get(user_id)
            if not user:
                session.clear()
                return jsonify({"error": "not authenticated"}), 401
            if roles and user.role not in roles:
                return jsonify({"error": "forbidden"}), 403
            return f(*args, user=user, **kwargs)
        return wrapped
    return decorator

def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)
