from models import db
from models.notification import Notification


def push_notification(app, socketio, user_id, title, body="", type="info", link=None):
    """Create a notification in the DB and push it via SocketIO."""
    with app.app_context():
        n = Notification(user_id=user_id, title=title, body=body, type=type, link=link)
        db.session.add(n)
        db.session.commit()
        socketio.emit("notification", n.to_dict(), room=f"user_{user_id}")
        return n.id
