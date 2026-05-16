from flask import request, jsonify
from api import blueprint
from auth import login_required
from models.library import Book, BookCheckout

@blueprint.route("/library/books", methods=["GET"])
@login_required()
def list_books(user):
    query = request.args.get("q", "").strip()
    books = Book.query.filter_by(school_id=user.school_id)
    if query:
        books = books.filter(Book.title.ilike(f"%{query}%") | Book.author.ilike(f"%{query}%"))
    return jsonify([b.to_dict() for b in books.all()])

@blueprint.route("/library/checked-out", methods=["GET"])
@login_required()
def checked_out(user):
    checkouts = (
        BookCheckout.query
        .filter_by(user_id=user.id, returned_at=None)
        .all()
    )
    return jsonify([c.to_dict() for c in checkouts])
