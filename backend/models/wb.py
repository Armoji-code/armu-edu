from models import db


class WbStroke(db.Model):
    __tablename__ = "wb_strokes"
    id        = db.Column(db.Integer, primary_key=True)
    room      = db.Column(db.String(200), nullable=False, index=True)
    stroke_id = db.Column(db.String(50), nullable=False)
    data      = db.Column(db.Text, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('room', 'stroke_id', name='uq_wb_room_stroke'),
    )
