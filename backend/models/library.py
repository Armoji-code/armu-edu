from models import db
from datetime import datetime, timezone

class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(200), nullable=False)
    isbn = db.Column(db.String(20), nullable=True)
    genre = db.Column(db.String(100), nullable=True)
    pages = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, default="")
    cover_url = db.Column(db.String(500), nullable=True)
    total_copies = db.Column(db.Integer, default=1)

    school = db.relationship("School", back_populates="books")
    checkouts = db.relationship("BookCheckout", back_populates="book")

    @property
    def available_copies(self):
        active = sum(1 for c in self.checkouts if c.returned_at is None)
        return self.total_copies - active

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "isbn": self.isbn,
            "genre": self.genre,
            "pages": self.pages,
            "description": self.description,
            "cover_url": self.cover_url,
            "total_copies": self.total_copies,
            "available_copies": self.available_copies,
        }


class BookCheckout(db.Model):
    __tablename__ = "book_checkouts"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    checked_out_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    due_date = db.Column(db.DateTime, nullable=False)
    returned_at = db.Column(db.DateTime, nullable=True)

    book = db.relationship("Book", back_populates="checkouts")
    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "book": self.book.to_dict() if self.book else None,
            "checked_out_at": self.checked_out_at.isoformat(),
            "due_date": self.due_date.isoformat(),
            "returned_at": self.returned_at.isoformat() if self.returned_at else None,
        }
