from models import db
from datetime import datetime, timezone

class AISession(db.Model):
    __tablename__ = "ai_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=True)
    title = db.Column(db.String(200), default="New Chat")
    model_tier = db.Column(db.Enum("standard", "advanced", name="model_tier"), default="standard")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User")
    group = db.relationship("Group", foreign_keys=[group_id])
    messages = db.relationship("AIMessage", back_populates="session", order_by="AIMessage.created_at")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "model_tier": self.model_tier,
            "created_at": self.created_at.isoformat(),
            "group_id": self.group_id,
            "group_name": self.group.name if self.group else None,
        }


class AIMessage(db.Model):
    __tablename__ = "ai_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("ai_sessions.id"), nullable=False)
    role = db.Column(db.Enum("user", "assistant", name="ai_role"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    session = db.relationship("AISession", back_populates="messages")
    sender = db.relationship("User", foreign_keys=[sender_id])

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "sender_id": self.sender_id,
            "sender_name": self.sender.name if self.sender else None,
        }
