"""Add users.role column

Revision ID: 0010_add_user_role
Revises: 0009_user_email_last_login
Create Date: 2026-01-12

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0010_add_user_role'
down_revision = '0009_user_email_last_login'
branch_labels = None
depends_on = None


def _get_columns(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col['name'] for col in inspector.get_columns(table_name)}


def upgrade():
    columns = _get_columns('users')
    if 'role' in columns:
        return

    # SQLite needs a server_default when adding a NOT NULL column.
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('role', sa.String(length=50), nullable=False, server_default='user')
        )


def downgrade():
    columns = _get_columns('users')
    if 'role' not in columns:
        return

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('role')
