import os
from flask import Flask, send_from_directory, abort
from flask_socketio import SocketIO
from flask_migrate import Migrate
from config import Config
from models import db

STATIC_DIR   = os.path.join(os.path.dirname(__file__), 'static')
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'pages')
PARTIALS_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'partials')

socketio = SocketIO()
migrate  = Migrate()

def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)

    if app.config["SECRET_KEY"] == "change-me-in-production":
        import warnings
        warnings.warn(
            "SECRET_KEY is set to the default insecure value. "
            "Set the SECRET_KEY environment variable before deploying.",
            stacklevel=2,
        )

    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins=app.config["CORS_ORIGINS"])

    from api import blueprint as api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    import websocket
    import websocket.meeting

    @app.route("/login")
    def login_page():
        return send_from_directory(FRONTEND_DIR, "login.html")

    @app.route("/partials/<path:filename>")
    def serve_partial(filename):
        return send_from_directory(PARTIALS_DIR, filename)

    @app.route("/static/<path:filename>")
    def serve_static(filename):
        return send_from_directory(STATIC_DIR, filename)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def shell(path):
        # Let Flask handle /api, /static, /partials internally
        if path.startswith(("api/", "static/", "partials/")):
            abort(404)
        return send_from_directory(FRONTEND_DIR, "app.html")

    import os
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from scheduler import init_scheduler
        init_scheduler(app, socketio)

    return app

if __name__ == "__main__":
    app = create_app()
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    socketio.run(app, debug=debug, allow_unsafe_werkzeug=True)
