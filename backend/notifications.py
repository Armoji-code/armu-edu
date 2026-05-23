from models import db
from models.notification import Notification


def push_notification(app, socketio, user_id, title, body="", type="info", link=None):
    """Create a notification in the DB, push via SocketIO, and send a web push."""
    with app.app_context():
        n = Notification(user_id=user_id, title=title, body=body, type=type, link=link)
        db.session.add(n)
        db.session.commit()
        socketio.emit("notification", n.to_dict(), room=f"user_{user_id}")
        try:
            from api.push import send_web_push
            send_web_push(app, user_id, title, body, link or '/')
        except Exception:
            pass
        return n.id
