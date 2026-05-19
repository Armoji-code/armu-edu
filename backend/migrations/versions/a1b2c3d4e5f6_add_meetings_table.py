"""add meetings table

Revision ID: a1b2c3d4e5f6
Revises: c5ed546857f6
Create Date: 2026-05-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'c5ed546857f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('meetings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('host_id', sa.Integer(), nullable=False),
    sa.Column('class_id', sa.Integer(), nullable=True),
    sa.Column('room_code', sa.String(length=8), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('ended_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ),
    sa.ForeignKeyConstraint(['host_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('room_code')
    )


def downgrade():
    op.drop_table('meetings')
