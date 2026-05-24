from datetime import datetime, timezone, timedelta
from flask import request, jsonify, Response, stream_with_context, current_app
from api import blueprint, err, ok
from auth import login_required
from models import db
from models.library import Book, BookCheckout
from models.user import User
from models.school import School
import requests as _req
import ai as _ai


def _school_id(user):
    return user.school_id


def _loan_dict(c):
    return {
        "id":             c.id,
        "book_id":        c.book_id,
        "book_title":     c.book.title if c.book else "",
        "book_author":    c.book.author if c.book else "",
        "user_id":        c.user_id,
        "user_name":      c.user.name if c.user else "",
        "user_email":     c.user.email if c.user else "",
        "checked_out_at": c.checked_out_at.isoformat(),
        "due_date":       c.due_date.isoformat(),
        "returned_at":    c.returned_at.isoformat() if c.returned_at else None,
        "overdue":        c.returned_at is None and c.due_date < datetime.now(timezone.utc).replace(tzinfo=None),
    }


# ── Overview ──────────────────────────────────────────────────────────────────

@blueprint.route("/librarian/overview", methods=["GET"])
@login_required(roles=["librarian"])
def librarian_overview(user):
    sid = _school_id(user)
    books    = Book.query.filter_by(school_id=sid).all()
    total_b  = len(books)
    total_c  = sum(b.total_copies for b in books)
    now      = datetime.now(timezone.utc).replace(tzinfo=None)
    active   = BookCheckout.query.join(Book).filter(
        Book.school_id == sid, BookCheckout.returned_at == None).all()
    checked  = len(active)
    overdue  = sum(1 for c in active if c.due_date < now)
    return jsonify({
        "total_books":   total_b,
        "total_copies":  total_c,
        "checked_out":   checked,
        "overdue":       overdue,
    })


# ── Books CRUD ────────────────────────────────────────────────────────────────

@blueprint.route("/librarian/books", methods=["GET"])
@login_required(roles=["librarian"])
def librarian_books(user):
    q = request.args.get("q", "").strip()
    books = Book.query.filter_by(school_id=_school_id(user))
    if q:
        books = books.filter(
            Book.title.ilike(f"%{q}%") |
            Book.author.ilike(f"%{q}%") |
            Book.isbn.ilike(f"%{q}%") |
            Book.genre.ilike(f"%{q}%")
        )
    return jsonify([b.to_dict() for b in books.order_by(Book.title).all()])


@blueprint.route("/librarian/books", methods=["POST"])
@login_required(roles=["librarian"])
def librarian_create_book(user):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    author = data.get("author", "").strip()
    if not title or not author:
        return err("title and author required", 400)
    b = Book(
        school_id    = _school_id(user),
        title        = title,
        author       = author,
        isbn         = data.get("isbn", "").strip() or None,
        genre        = data.get("genre", "").strip() or None,
        pages        = int(data["pages"]) if data.get("pages") else None,
        description  = data.get("description", "").strip(),
        cover_url    = data.get("cover_url", "").strip() or None,
        total_copies = max(1, int(data.get("total_copies", 1))),
    )
    db.session.add(b)
    db.session.commit()
    return jsonify(b.to_dict()), 201


@blueprint.route("/librarian/books/<int:book_id>", methods=["PATCH"])
@login_required(roles=["librarian"])
def librarian_update_book(user, book_id):
    b = Book.query.filter_by(id=book_id, school_id=_school_id(user)).first_or_404()
    data = request.get_json(silent=True) or {}
    if "title"  in data and data["title"].strip():  b.title  = data["title"].strip()
    if "author" in data and data["author"].strip():  b.author = data["author"].strip()
    if "isbn"   in data:  b.isbn  = data["isbn"].strip() or None
    if "genre"  in data:  b.genre = data["genre"].strip() or None
    if "pages"  in data:  b.pages = int(data["pages"]) if data["pages"] else None
    if "description" in data: b.description = data["description"].strip()
    if "cover_url"   in data: b.cover_url   = data["cover_url"].strip() or None
    if "total_copies" in data:
        new_copies = max(1, int(data["total_copies"]))
        active = sum(1 for c in b.checkouts if c.returned_at is None)
        if new_copies < active:
            return jsonify({"error": f"Cannot reduce below {active} (currently checked out)"}), 400
        b.total_copies = new_copies
    db.session.commit()
    return jsonify(b.to_dict())


@blueprint.route("/librarian/books/<int:book_id>", methods=["DELETE"])
@login_required(roles=["librarian"])
def librarian_delete_book(user, book_id):
    b = Book.query.filter_by(id=book_id, school_id=_school_id(user)).first_or_404()
    active = sum(1 for c in b.checkouts if c.returned_at is None)
    if active:
        return jsonify({"error": f"{active} cop{'y' if active==1 else 'ies'} currently checked out"}), 400
    db.session.delete(b)
    db.session.commit()
    return ok()


# ── Loans ─────────────────────────────────────────────────────────────────────

@blueprint.route("/librarian/loans", methods=["GET"])
@login_required(roles=["librarian"])
def librarian_loans(user):
    sid    = _school_id(user)
    status = request.args.get("status", "active")  # active | overdue | all
    now    = datetime.now(timezone.utc).replace(tzinfo=None)
    q = BookCheckout.query.join(Book).filter(Book.school_id == sid)
    if status == "active":
        q = q.filter(BookCheckout.returned_at == None)
    elif status == "overdue":
        q = q.filter(BookCheckout.returned_at == None, BookCheckout.due_date < now)
    loans = q.order_by(BookCheckout.due_date).all()
    return jsonify([_loan_dict(c) for c in loans])


@blueprint.route("/librarian/loans", methods=["POST"])
@login_required(roles=["librarian"])
def librarian_checkout(user):
    data    = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    user_id = data.get("user_id")
    due_str = data.get("due_date")
    if not book_id or not user_id or not due_str:
        return err("book_id, user_id, due_date required", 400)

    book = Book.query.filter_by(id=book_id, school_id=_school_id(user)).first_or_404()
    if book.available_copies < 1:
        return err("No copies available", 400)

    due = datetime.fromisoformat(due_str)
    c = BookCheckout(book_id=book_id, user_id=user_id, due_date=due)
    db.session.add(c)
    db.session.flush()  # write within transaction so count query sees it

    active = BookCheckout.query.filter_by(book_id=book_id, returned_at=None).count()
    if active > book.total_copies:
        db.session.rollback()
        return err("No copies available", 400)

    db.session.commit()
    return jsonify(_loan_dict(c)), 201


@blueprint.route("/librarian/loans/<int:loan_id>/return", methods=["POST"])
@login_required(roles=["librarian"])
def librarian_return(user, loan_id):
    c = BookCheckout.query.join(Book).filter(
        BookCheckout.id == loan_id,
        Book.school_id == _school_id(user)
    ).first_or_404()
    if c.returned_at:
        return err("Already returned", 400)
    c.returned_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    return jsonify(_loan_dict(c))


# ── Book lookup helpers ───────────────────────────────────────────────────────

@blueprint.route("/librarian/book-covers", methods=["GET"])
@login_required(roles=["librarian"])
def librarian_book_covers(user):
    title  = request.args.get("title", "").strip()
    author = request.args.get("author", "").strip()
    if not title:
        return err("title required", 400)

    # Subjects that are metadata noise, not actual genres
    _SKIP_SUBJECTS = {
        "accessible book", "protected daisy", "open library staff picks",
        "large type books", "in library", "internet archive wishlist",
        "overdrive", "nonfiction", "fiction", "juvenile fiction",
        "juvenile nonfiction", "children's fiction", "children's nonfiction",
        "english language", "reading level",
    }

    try:
        params = {"limit": 20, "fields": "cover_i,title,author_name,subject"}
        if title:  params["title"]  = title
        if author: params["author"] = author
        resp = _req.get("https://openlibrary.org/search.json", params=params, timeout=6)
        docs = resp.json().get("docs", [])

        # Collect up to 3 distinct cover IDs
        seen_covers, urls = set(), []
        found_author, found_genre = None, None

        for d in docs:
            # Author — take from first result that has one
            if not found_author:
                names = d.get("author_name") or []
                if names:
                    found_author = names[0]

            # Genre — pick first short, non-noise subject
            if not found_genre:
                for s in (d.get("subject") or []):
                    if len(s) <= 40 and s.lower() not in _SKIP_SUBJECTS:
                        found_genre = s
                        break

            cid = d.get("cover_i")
            if cid and cid not in seen_covers:
                seen_covers.add(cid)
                urls.append(f"https://covers.openlibrary.org/b/id/{cid}-L.jpg")

            if len(urls) == 3 and found_author and found_genre:
                break

        return jsonify({"covers": urls, "author": found_author, "genre": found_genre})
    except Exception as e:
        return jsonify({"covers": [], "author": None, "genre": None, "error": str(e)})


@blueprint.route("/librarian/book-description", methods=["GET"])
@login_required(roles=["librarian"])
def librarian_book_description(user):
    title  = request.args.get("title", "").strip()
    author = request.args.get("author", "").strip()
    if not title:
        return err("title required", 400)

    ai_cfg = _ai.get_ai_config()
    model  = ai_cfg["tracker_model"]
    prompt = (
        f'Write a concise 2-3 sentence library catalog description for the book '
        f'"{title}"{(" by " + author) if author else ""}. '
        f'Describe the plot and genre briefly. Do not use the phrases "this book" or '
        f'"the book". Just output the description, nothing else.'
    )

    def generate():
        try:
            for token in _ai.stream(model=model, messages=[{"role": "user", "content": prompt}],
                                    temperature=ai_cfg["tracker_temperature"]):
                yield token
        except Exception as e:
            yield f"\n[Error: {e}]"

    return Response(stream_with_context(generate()), mimetype="text/plain")


# ── Members (students to check out to) ───────────────────────────────────────

@blueprint.route("/librarian/members", methods=["GET"])
@login_required(roles=["librarian"])
def librarian_members(user):
    q = request.args.get("q", "").strip()
    members = User.query.filter(
        User.school_id == _school_id(user),
        User.role.in_(["student", "teacher"])
    )
    if q:
        members = members.filter(
            User.name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%")
        )
    return jsonify([{"id": u.id, "name": u.name, "email": u.email, "role": u.role}
                    for u in members.order_by(User.name).limit(50).all()])
