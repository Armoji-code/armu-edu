"""add nav_configs table

Revision ID: 47d93957f4d4
Revises: a1b2c3d4e5f6
Create Date: 2026-05-19 21:36:32.014026

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '47d93957f4d4'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('nav_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('sections', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role', name='uq_nav_configs_role')
    )


def downgrade():
    op.drop_table('nav_configs')
