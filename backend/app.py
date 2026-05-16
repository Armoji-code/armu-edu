import os
from flask import Flask, send_from_directory
from flask_socketio import SocketIO
from flask_migrate import Migrate
from config import Config
from models import db

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

    return app

if __name__ == "__main__":
    app = create_app()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
