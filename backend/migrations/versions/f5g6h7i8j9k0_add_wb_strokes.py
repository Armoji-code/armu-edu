"""add wb_strokes

Revision ID: f5g6h7i8j9k0
Revises: d3e4f5a6b7c8
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa

revision = 'f5g6h7i8j9k0'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'wb_strokes',
        sa.Column('id',        sa.Integer(),     nullable=False),
        sa.Column('room',      sa.String(200),   nullable=False),
        sa.Column('stroke_id', sa.String(50),    nullable=False),
        sa.Column('data',      sa.Text(),        nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('room', 'stroke_id', name='uq_wb_room_stroke'),
    )
    op.create_index('ix_wb_strokes_room', 'wb_strokes', ['room'])


def downgrade():
    op.drop_index('ix_wb_strokes_room', table_name='wb_strokes')
    op.drop_table('wb_strokes')
