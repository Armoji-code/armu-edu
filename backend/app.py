import os
from flask import Flask, send_from_directory
from flask_socketio import SocketIO
from flask_migrate import Migrate
from config import Config
from models import db

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'pages')

socketio = SocketIO()
migrate = Migrate()

def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)

    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins="*")

    from api import blueprint as api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    import websocket  # registers SocketIO event handlers

    @app.route("/")
    @app.route("/login")
    def login_page():
        return send_from_directory(FRONTEND_DIR, "login.html")

    @app.route("/dashboard")
    def dashboard_page():
        return send_from_directory(FRONTEND_DIR, "dashboard.html")

    @app.route("/calendar")
    def calendar_page():
        return send_from_directory(FRONTEND_DIR, "calendar.html")

    @app.route("/homework")
    def homework_page():
        return send_from_directory(FRONTEND_DIR, "homework.html")

    @app.route("/tests")
    def tests_page():
        return send_from_directory(FRONTEND_DIR, "tests.html")

    @app.route("/schedule")
    def schedule_page():
        return send_from_directory(FRONTEND_DIR, "schedule.html")

    @app.route("/grades")
    def grades_page():
        return send_from_directory(FRONTEND_DIR, "grades.html")

    @app.route("/leaderboard")
    def leaderboard_page():
        return send_from_directory(FRONTEND_DIR, "leaderboard.html")

    @app.route("/conduct")
    def conduct_page():
        return send_from_directory(FRONTEND_DIR, "conduct.html")

    @app.route("/activities")
    def activities_page():
        return send_from_directory(FRONTEND_DIR, "activities.html")

    @app.route("/whiteboard")
    def whiteboard_page():
        return send_from_directory(FRONTEND_DIR, "whiteboard.html")

    @app.route("/groups")
    def groups_page():
        return send_from_directory(FRONTEND_DIR, "groups.html")

    @app.route("/library")
    def library_page():
        return send_from_directory(FRONTEND_DIR, "library.html")

    @app.route("/messages")
    def messages_page():
        return send_from_directory(FRONTEND_DIR, "messages.html")

    @app.route("/tutor")
    def tutor_page():
        return send_from_directory(FRONTEND_DIR, "tutor.html")

    @app.route("/profile")
    def profile_page():
        return send_from_directory(FRONTEND_DIR, "profile.html")

    @app.route("/settings")
    def settings_page():
        return send_from_directory(FRONTEND_DIR, "settings.html")

    @app.route("/teacher")
    def teacher_dashboard_page():
        return send_from_directory(FRONTEND_DIR, "teacher_dashboard.html")

    @app.route("/teacher/classes")
    def teacher_classes_page():
        return send_from_directory(FRONTEND_DIR, "teacher_classes.html")

    @app.route("/teacher/assignments")
    def teacher_assignments_page():
        return send_from_directory(FRONTEND_DIR, "teacher_assignments.html")

    @app.route("/admin")
    def admin_dashboard_page():
        return send_from_directory(FRONTEND_DIR, "admin_dashboard.html")

    @app.route("/admin/users")
    def admin_users_page():
        return send_from_directory(FRONTEND_DIR, "admin_users.html")

    @app.route("/admin/school")
    def admin_school_page():
        return send_from_directory(FRONTEND_DIR, "admin_school.html")

    @app.route("/admin/settings")
    def admin_settings_page():
        return send_from_directory(FRONTEND_DIR, "admin_settings.html")

    @app.route("/static/<path:filename>")
    def serve_static(filename):
        return send_from_directory(STATIC_DIR, filename)

    import os
    # Only start scheduler in the main process (not the Werkzeug reloader child)
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from scheduler import init_scheduler
        init_scheduler(app, socketio)

    return app

if __name__ == "__main__":
    app = create_app()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
