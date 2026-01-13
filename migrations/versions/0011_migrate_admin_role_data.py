"""Migrate existing admin users to role-based system

Revision ID: 0011_migrate_admin_role_data
Revises: 0010_add_user_role
Create Date: 2026-01-13

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0011_migrate_admin_role_data'
down_revision = '0010_add_user_role'
branch_labels = None
depends_on = None


def upgrade():
    """
    Migrate users from is_admin Boolean to role-based system.
    
    This must happen AFTER 0010_add_user_role adds the role column.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('users')}
    
    # Only proceed if both old (is_admin) and new (role) columns exist
    if 'is_admin' not in columns or 'role' not in columns:
        return
    
    # Update existing admins to superadmin role
    bind.execute(
        sa.text(
            "UPDATE users SET role = 'superadmin' "
            "WHERE is_admin = 1 OR is_admin = true"
        )
    )
    
    # Update non-admin users to 'user' role (should already be default, but explicit is better)
    bind.execute(
        sa.text(
            "UPDATE users SET role = 'user' "
            "WHERE (is_admin = 0 OR is_admin = false OR is_admin IS NULL) "
            "AND role != 'superadmin'"
        )
    )
    
    # Drop the obsolete is_admin column
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('is_admin')


def downgrade():
    """
    Restore is_admin Boolean column and repopulate from role.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('users')}
    
    # Re-add is_admin column if missing
    if 'is_admin' not in columns:
        with op.batch_alter_table('users') as batch_op:
            batch_op.add_column(
                sa.Column('is_admin', sa.Boolean(), nullable=True, server_default='false')
            )
    
    # Restore is_admin values from role
    bind.execute(
        sa.text(
            "UPDATE users SET is_admin = 1 "
            "WHERE role = 'superadmin'"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE users SET is_admin = 0 "
            "WHERE role != 'superadmin'"
        )
    )
