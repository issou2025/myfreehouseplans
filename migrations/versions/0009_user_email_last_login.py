"""Add user email and last_login columns

Revision ID: 0009_user_email_last_login
Revises: 0008_visitor_tracking
Create Date: 2026-01-12

"""

from alembic import op
import sqlalchemy as sa


def _get_columns(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col['name'] for col in inspector.get_columns(table_name)}


def _get_indexes(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {idx['name'] for idx in inspector.get_indexes(table_name)}


# revision identifiers, used by Alembic.
revision = '0009_user_email_last_login'
down_revision = '0008_visitor_tracking'
branch_labels = None
depends_on = None


def upgrade():
    existing_columns = _get_columns('users')

    with op.batch_alter_table('users') as batch_op:
        if 'email' not in existing_columns:
            batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))
        if 'last_login' not in existing_columns:
            batch_op.add_column(sa.Column('last_login', sa.DateTime(), nullable=True))

    if 'ix_users_email' not in _get_indexes('users'):
        op.create_index('ix_users_email', 'users', ['email'], unique=True)


def downgrade():
    indexes = _get_indexes('users')
    if 'ix_users_email' in indexes:
        op.drop_index('ix_users_email', table_name='users')

    columns = _get_columns('users')
    with op.batch_alter_table('users') as batch_op:
        if 'last_login' in columns:
            batch_op.drop_column('last_login')
        if 'email' in columns:
            batch_op.drop_column('email')
