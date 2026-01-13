"""Add performance indexes for house plans queries

Revision ID: 0012_add_performance_indexes
Revises: 0011_migrate_admin_role_data
Create Date: 2026-01-13

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0012_add_performance_indexes'
down_revision = '0011_migrate_admin_role_data'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add indexes to optimize common query patterns.
    
    These indexes support:
    - Homepage plan listing (published + sorted by views/created_at)
    - Category filtering (published plans in category)
    - Search queries (published plans by type)
    """
    # Composite index for published plans sorted by popularity
    op.create_index(
        'ix_house_plans_published_views',
        'house_plans',
        ['is_published', 'views_count'],
        unique=False
    )
    
    # Composite index for published plans sorted by recency
    op.create_index(
        'ix_house_plans_published_created',
        'house_plans',
        ['is_published', 'created_at'],
        unique=False
    )
    
    # Index for plan type filtering
    op.create_index(
        'ix_house_plans_plan_type',
        'house_plans',
        ['plan_type'],
        unique=False
    )
    
    # Index for featured plans
    op.create_index(
        'ix_house_plans_featured',
        'house_plans',
        ['is_featured'],
        unique=False
    )


def downgrade():
    """Remove performance indexes"""
    op.drop_index('ix_house_plans_featured', table_name='house_plans')
    op.drop_index('ix_house_plans_plan_type', table_name='house_plans')
    op.drop_index('ix_house_plans_published_created', table_name='house_plans')
    op.drop_index('ix_house_plans_published_views', table_name='house_plans')
