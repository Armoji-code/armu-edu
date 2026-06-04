"""add sports join requests

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-06-04 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'h2i3j4k5l6m7'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sports_join_requests',
        sa.Column('id',         sa.Integer(),     nullable=False),
        sa.Column('team_id',    sa.Integer(),     nullable=False),
        sa.Column('user_id',    sa.Integer(),     nullable=False),
        sa.Column('status',     sa.String(20),    nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(),    nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['sports_teams.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'user_id'),
    )


def downgrade():
    op.drop_table('sports_join_requests')
