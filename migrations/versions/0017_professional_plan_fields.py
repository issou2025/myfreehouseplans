"""Add professional plan fields (safe additive only)

Revision ID: 0017_professional_plan_fields
Revises: 0016_request_logs
Create Date: 2026-01-26 12:30:00.000000

IMPORTANT: This migration only ADDS new nullable columns.
It does NOT delete, rename, or modify any existing columns.
All existing plans will continue to work without errors.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0017_professional_plan_fields'
down_revision = '0016_request_logs'
branch_labels = None
depends_on = None


def upgrade():
    """Add new professional fields to house_plans table.
    
    All fields are nullable to ensure compatibility with existing data.
    """
    
    # Reference system: new public plan code (MFP-XXX format)
    op.add_column('house_plans', sa.Column('public_plan_code', sa.String(length=20), nullable=True))
    op.create_index('ix_house_plans_public_plan_code', 'house_plans', ['public_plan_code'], unique=True)
    
    # Marketing fields
    op.add_column('house_plans', sa.Column('target_buyer', sa.String(length=200), nullable=True))
    op.add_column('house_plans', sa.Column('budget_category', sa.String(length=100), nullable=True))
    op.add_column('house_plans', sa.Column('key_selling_point', sa.String(length=500), nullable=True))
    op.add_column('house_plans', sa.Column('problems_this_plan_solves', sa.Text(), nullable=True))
    
    # Structured room details
    op.add_column('house_plans', sa.Column('living_rooms', sa.Integer(), nullable=True))
    op.add_column('house_plans', sa.Column('kitchens', sa.Integer(), nullable=True))
    op.add_column('house_plans', sa.Column('offices', sa.Integer(), nullable=True))
    op.add_column('house_plans', sa.Column('terraces', sa.Integer(), nullable=True))
    op.add_column('house_plans', sa.Column('storage_rooms', sa.Integer(), nullable=True))
    
    # Land requirements (metric: meters)
    op.add_column('house_plans', sa.Column('min_plot_width', sa.Float(), nullable=True))
    op.add_column('house_plans', sa.Column('min_plot_length', sa.Float(), nullable=True))
    
    # Construction details
    op.add_column('house_plans', sa.Column('climate_compatibility', sa.String(length=300), nullable=True))
    op.add_column('house_plans', sa.Column('estimated_build_time', sa.String(length=150), nullable=True))
    
    # Cost estimates (USD)
    op.add_column('house_plans', sa.Column('estimated_cost_low', sa.Float(), nullable=True))
    op.add_column('house_plans', sa.Column('estimated_cost_high', sa.Float(), nullable=True))
    
    # Pack descriptions (what's included in each download)
    op.add_column('house_plans', sa.Column('pack1_description', sa.Text(), nullable=True))
    op.add_column('house_plans', sa.Column('pack2_description', sa.Text(), nullable=True))
    op.add_column('house_plans', sa.Column('pack3_description', sa.Text(), nullable=True))
    
    # Architectural style (new explicit field, separate from plan_type)
    op.add_column('house_plans', sa.Column('architectural_style', sa.String(length=150), nullable=True))


def downgrade():
    """Remove added columns (safe rollback)."""
    
    op.drop_index('ix_house_plans_public_plan_code', table_name='house_plans')
    op.drop_column('house_plans', 'public_plan_code')
    
    op.drop_column('house_plans', 'target_buyer')
    op.drop_column('house_plans', 'budget_category')
    op.drop_column('house_plans', 'key_selling_point')
    op.drop_column('house_plans', 'problems_this_plan_solves')
    
    op.drop_column('house_plans', 'living_rooms')
    op.drop_column('house_plans', 'kitchens')
    op.drop_column('house_plans', 'offices')
    op.drop_column('house_plans', 'terraces')
    op.drop_column('house_plans', 'storage_rooms')
    
    op.drop_column('house_plans', 'min_plot_width')
    op.drop_column('house_plans', 'min_plot_length')
    
    op.drop_column('house_plans', 'climate_compatibility')
    op.drop_column('house_plans', 'estimated_build_time')
    
    op.drop_column('house_plans', 'estimated_cost_low')
    op.drop_column('house_plans', 'estimated_cost_high')
    
    op.drop_column('house_plans', 'pack1_description')
    op.drop_column('house_plans', 'pack2_description')
    op.drop_column('house_plans', 'pack3_description')
    
    op.drop_column('house_plans', 'architectural_style')
