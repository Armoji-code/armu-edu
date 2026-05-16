from flask import Flask
from flask_socketio import SocketIO
from flask_migrate import Migrate
from config import Config
from models import db

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

    return app

if __name__ == "__main__":
    app = create_app()
    socketio.run(app, debug=True)
