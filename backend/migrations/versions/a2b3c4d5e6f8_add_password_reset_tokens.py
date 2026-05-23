"""add password_reset_tokens table

Revision ID: a2b3c4d5e6f8
Revises: f2e3d4c5b6a7
Create Date: 2026-05-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a2b3c4d5e6f8'
down_revision = 'f2e3d4c5b6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'password_reset_tokens',
        sa.Column('id',         sa.Integer(),     nullable=False),
        sa.Column('user_id',    sa.Integer(),     nullable=False),
        sa.Column('token_hash', sa.String(64),    nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used',       sa.Boolean(),     nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('password_reset_tokens')
