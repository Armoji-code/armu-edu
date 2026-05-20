from models import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum("student", "teacher", "librarian", "admin", "parent", name="user_role"), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=True)
    parent_of_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    can_change_password = db.Column(db.Boolean, default=True, nullable=False, server_default='1')

    school = db.relationship("School", back_populates="users")
    klass = db.relationship("Class", back_populates="students", foreign_keys=[class_id])
    child = db.relationship("User", remote_side=[id], foreign_keys=[parent_of_id])

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "school_id": self.school_id,
            "school_name": self.school.name if self.school else None,
            "class_id": self.class_id,
            "class_name": self.klass.name if self.klass else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "can_change_password": self.can_change_password,
        }
