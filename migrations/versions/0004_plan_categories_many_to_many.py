"""Plan categories many-to-many

Revision ID: 0004_plan_categories_many_to_many
Revises: 0003_add_architectural_characteristics
Create Date: 2026-01-09

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_plan_categories_many_to_many'
down_revision = '0003_add_architectural_characteristics'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # Create association table if missing (production-safe; does not drop/rename anything).
    if 'house_plan_categories' not in existing_tables:
        op.create_table(
            'house_plan_categories',
            sa.Column('plan_id', sa.Integer(), sa.ForeignKey('house_plans.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id', ondelete='CASCADE'), primary_key=True),
        )
        op.create_index('ix_house_plan_categories_plan_id', 'house_plan_categories', ['plan_id'], unique=False)
        op.create_index('ix_house_plan_categories_category_id', 'house_plan_categories', ['category_id'], unique=False)

    # Backfill from legacy one-to-many column if present.
    # IMPORTANT: Use dialect-safe SQL (SQLite vs PostgreSQL).
    house_plans_cols = {col['name'] for col in inspector.get_columns('house_plans')}
    if 'category_id' in house_plans_cols:
        dialect = bind.dialect.name
        if dialect == 'sqlite':
            op.execute(
                """
                INSERT OR IGNORE INTO house_plan_categories (plan_id, category_id)
                SELECT id AS plan_id, category_id
                FROM house_plans
                WHERE category_id IS NOT NULL
                """
            )
        else:
            op.execute(
                """
                INSERT INTO house_plan_categories (plan_id, category_id)
                SELECT id AS plan_id, category_id
                FROM house_plans
                WHERE category_id IS NOT NULL
                ON CONFLICT DO NOTHING
                """
            )

    # NOTE: We intentionally DO NOT drop the legacy `house_plans.category_id` column.
    # Leaving it in place is non-destructive and keeps legacy data intact.


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'house_plan_categories' not in tables:
        return

    house_plans_cols = {col['name'] for col in inspector.get_columns('house_plans')}
    if 'category_id' not in house_plans_cols:
        with op.batch_alter_table('house_plans') as batch_op:
            batch_op.add_column(sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id')))

    # Best-effort restore: pick the first category per plan.
    op.execute(
        """
        UPDATE house_plans
        SET category_id = (
            SELECT category_id
            FROM house_plan_categories
            WHERE house_plan_categories.plan_id = house_plans.id
            ORDER BY category_id ASC
            LIMIT 1
        )
        """
    )

    # Drop association artifacts.
    try:
        op.drop_index('ix_house_plan_categories_category_id', table_name='house_plan_categories')
    except Exception:
        pass
    try:
        op.drop_index('ix_house_plan_categories_plan_id', table_name='house_plan_categories')
    except Exception:
        pass
    op.drop_table('house_plan_categories')
