"""add flagged_messages table

Revision ID: e1f2a3b4c5d6
Revises: b9e8d7c6a5f4
Create Date: 2026-05-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e1f2a3b4c5d6'
down_revision = 'b9e8d7c6a5f4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'flagged_messages',
        sa.Column('id',         sa.Integer(),     nullable=False),
        sa.Column('message_id', sa.Integer(),     nullable=False),
        sa.Column('severity',   sa.Float(),       nullable=True),
        sa.Column('reason',     sa.Text(),        nullable=True),
        sa.Column('status',     sa.String(20),    nullable=True),
        sa.Column('flagged_at', sa.DateTime(),    nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('flagged_messages')
