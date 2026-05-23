from models import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
import secrets, hashlib

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
    preferences = db.Column(db.JSON, nullable=True, default=None)

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


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used       = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref="reset_tokens")

    @staticmethod
    def generate(user_id: int, ttl_minutes: int = 15):
        code = f"{secrets.randbelow(1000000):06d}"
        token_hash = hashlib.sha256(code.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        obj = PasswordResetToken(user_id=user_id, token_hash=token_hash,
                                 expires_at=expires_at)
        return obj, code

    @staticmethod
    def verify(user_id: int, code: str):
        token_hash = hashlib.sha256(code.encode()).hexdigest()
        now = datetime.now(timezone.utc)
        return PasswordResetToken.query.filter_by(
            user_id=user_id, token_hash=token_hash, used=False
        ).filter(PasswordResetToken.expires_at > now).first()
