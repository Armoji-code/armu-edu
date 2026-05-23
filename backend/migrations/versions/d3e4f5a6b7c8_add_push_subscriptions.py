"""add push subscriptions

Revision ID: d3e4f5a6b7c8
Revises: a2b3c4d5e6f8
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa

revision = 'd3e4f5a6b7c8'
down_revision = 'a2b3c4d5e6f8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'push_subscriptions',
        sa.Column('id',         sa.Integer(),  nullable=False),
        sa.Column('user_id',    sa.Integer(),  nullable=False),
        sa.Column('endpoint',   sa.Text(),     nullable=False),
        sa.Column('p256dh',     sa.Text(),     nullable=False),
        sa.Column('auth',       sa.Text(),     nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('endpoint'),
    )


def downgrade():
    op.drop_table('push_subscriptions')
