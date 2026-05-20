"""add can_change_password to users

Revision ID: f7cae663b420
Revises: 47d93957f4d4
Create Date: 2026-05-20 12:32:21.994052

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7cae663b420'
down_revision = '47d93957f4d4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('can_change_password', sa.Boolean(), server_default='1', nullable=False))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('can_change_password')
