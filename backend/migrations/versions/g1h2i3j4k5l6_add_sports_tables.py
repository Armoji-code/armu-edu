"""add sports tables

Revision ID: g1h2i3j4k5l6
Revises: f5g6h7i8j9k0
Create Date: 2026-06-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'g1h2i3j4k5l6'
down_revision = 'f5g6h7i8j9k0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sports_teams',
        sa.Column('id',          sa.Integer(),     nullable=False),
        sa.Column('school_id',   sa.Integer(),     nullable=False),
        sa.Column('name',        sa.String(150),   nullable=False),
        sa.Column('sport',       sa.String(100),   nullable=False),
        sa.Column('description', sa.Text(),        nullable=True),
        sa.Column('coach_id',    sa.Integer(),     nullable=True),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.ForeignKeyConstraint(['coach_id'],  ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('sports_games',
        sa.Column('id',         sa.Integer(),  nullable=False),
        sa.Column('team_id',    sa.Integer(),  nullable=False),
        sa.Column('date',       sa.DateTime(), nullable=False),
        sa.Column('opponent',   sa.String(200), nullable=False),
        sa.Column('location',   sa.String(300), nullable=True),
        sa.Column('home_score', sa.Integer(),  nullable=True),
        sa.Column('away_score', sa.Integer(),  nullable=True),
        sa.Column('status',     sa.Enum('upcoming', 'completed', 'cancelled', name='game_status'), nullable=False, server_default='upcoming'),
        sa.ForeignKeyConstraint(['team_id'], ['sports_teams.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('sports_team_members',
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['sports_teams.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('team_id', 'user_id'),
    )


def downgrade():
    op.drop_table('sports_team_members')
    op.drop_table('sports_games')
    op.drop_table('sports_teams')
    op.execute("DROP TYPE IF EXISTS game_status")
