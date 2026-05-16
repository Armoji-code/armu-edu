from models import db
from datetime import datetime, timezone

group_members = db.Table(
    "group_members",
    db.Column("group_id", db.Integer, db.ForeignKey("groups.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
)


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=True)

    members = db.relationship("User", secondary=group_members)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "class_id": self.class_id}


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=True)
    content = db.Column(db.Text, nullable=False)
    file_url = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])
    group = db.relationship("Group")

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_name": self.sender.name if self.sender else None,
            "recipient_id": self.recipient_id,
            "group_id": self.group_id,
            "content": self.content,
            "file_url": self.file_url,
            "file_name": self.file_name,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat(),
        }


activity_enrollments = db.Table(
    "activity_enrollments",
    db.Column("activity_id", db.Integer, db.ForeignKey("activities.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
)

ActivityEnrollment = activity_enrollments


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    type = db.Column(db.Enum("club", "sport", "team", "other", name="activity_type"), nullable=False, default="club")
    description = db.Column(db.Text, default="")

    members = db.relationship("User", secondary=activity_enrollments)
    events = db.relationship("ActivityEvent", back_populates="activity")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "type": self.type, "description": self.description}


class ActivityEvent(db.Model):
    __tablename__ = "activity_events"

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    date = db.Column(db.DateTime, nullable=False)

    activity = db.relationship("Activity", back_populates="events")

    def to_dict(self):
        return {
            "id": self.id,
            "activity_id": self.activity_id,
            "title": self.title,
            "description": self.description,
            "date": self.date.isoformat(),
        }


class CommunityService(db.Model):
    __tablename__ = "community_service"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    organization = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    hours = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False)

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "organization": self.organization,
            "description": self.description,
            "hours": self.hours,
            "date": self.date.isoformat(),
        }
