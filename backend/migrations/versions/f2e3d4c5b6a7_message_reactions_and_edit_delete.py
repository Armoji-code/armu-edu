"""add message reactions, edit, delete, reply

Revision ID: f2e3d4c5b6a7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f2e3d4c5b6a7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('messages', sa.Column('is_deleted',  sa.Boolean(),  nullable=True, server_default='0'))
    op.add_column('messages', sa.Column('edited_at',   sa.DateTime(), nullable=True))
    op.add_column('messages', sa.Column('reply_to_id', sa.Integer(),  nullable=True))
    with op.batch_alter_table('messages') as batch:
        batch.create_foreign_key('fk_messages_reply_to', 'messages', ['reply_to_id'], ['id'])

    op.create_table(
        'message_reactions',
        sa.Column('id',         sa.Integer(),  nullable=False),
        sa.Column('message_id', sa.Integer(),  nullable=False),
        sa.Column('user_id',    sa.Integer(),  nullable=False),
        sa.Column('emoji',      sa.String(10), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id']),
        sa.ForeignKeyConstraint(['user_id'],    ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id', 'user_id', 'emoji', name='uq_msg_reaction'),
    )


def downgrade():
    op.drop_table('message_reactions')
    with op.batch_alter_table('messages') as batch:
        batch.drop_constraint('fk_messages_reply_to', type_='foreignkey')
        batch.drop_column('reply_to_id')
        batch.drop_column('edited_at')
        batch.drop_column('is_deleted')
