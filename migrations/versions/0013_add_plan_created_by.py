"""Add created_by to house plans

Revision ID: 0013_add_plan_created_by
Revises: 0012_add_performance_indexes
Create Date: 2026-01-14

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0013_add_plan_created_by'
down_revision = '0012_add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {col['name'] for col in inspector.get_columns('house_plans')}
    if 'created_by_id' not in existing_columns:
        op.add_column(
            'house_plans',
            sa.Column('created_by_id', sa.Integer(), nullable=True),
        )

    existing_indexes = {idx['name'] for idx in inspector.get_indexes('house_plans')}
    if 'ix_house_plans_created_by_id' not in existing_indexes:
        op.create_index('ix_house_plans_created_by_id', 'house_plans', ['created_by_id'], unique=False)

    # SQLite cannot add foreign keys via ALTER TABLE in the same way as Postgres.
    if bind.dialect.name != 'sqlite':
        existing_fks = {fk.get('name') for fk in inspector.get_foreign_keys('house_plans')}
        if 'fk_house_plans_created_by_id_users' not in existing_fks:
            op.create_foreign_key(
                'fk_house_plans_created_by_id_users',
                'house_plans',
                'users',
                ['created_by_id'],
                ['id'],
                ondelete='SET NULL',
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {col['name'] for col in inspector.get_columns('house_plans')}
    if 'created_by_id' not in existing_columns:
        return

    if bind.dialect.name != 'sqlite':
        existing_fks = {fk.get('name') for fk in inspector.get_foreign_keys('house_plans')}
        if 'fk_house_plans_created_by_id_users' in existing_fks:
            op.drop_constraint('fk_house_plans_created_by_id_users', 'house_plans', type_='foreignkey')

    existing_indexes = {idx['name'] for idx in inspector.get_indexes('house_plans')}
    if 'ix_house_plans_created_by_id' in existing_indexes:
        op.drop_index('ix_house_plans_created_by_id', table_name='house_plans')

    op.drop_column('house_plans', 'created_by_id')
