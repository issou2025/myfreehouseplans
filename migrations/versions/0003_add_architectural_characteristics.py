"""Add architectural characteristics to house plans

Revision ID: 0003_add_architectural_characteristics
Revises: 0002_add_gumroad_links
Create Date: 2026-01-09

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_add_architectural_characteristics'
down_revision = '0002_add_gumroad_links'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('house_plans', sa.Column('total_area_m2', sa.Float(), nullable=True))
    op.add_column('house_plans', sa.Column('total_area_sqft', sa.Float(), nullable=True))
    op.add_column('house_plans', sa.Column('number_of_bedrooms', sa.Integer(), nullable=True))
    op.add_column('house_plans', sa.Column('number_of_bathrooms', sa.Float(), nullable=True))
    op.add_column('house_plans', sa.Column('number_of_floors', sa.Integer(), nullable=True))
    op.add_column('house_plans', sa.Column('building_width', sa.Float(), nullable=True))
    op.add_column('house_plans', sa.Column('building_length', sa.Float(), nullable=True))
    op.add_column('house_plans', sa.Column('roof_type', sa.String(length=100), nullable=True))
    op.add_column('house_plans', sa.Column('structure_type', sa.String(length=120), nullable=True))
    op.add_column('house_plans', sa.Column('foundation_type', sa.String(length=120), nullable=True))
    op.add_column('house_plans', sa.Column('parking_spaces', sa.Integer(), nullable=True))
    op.add_column('house_plans', sa.Column('ceiling_height', sa.Float(), nullable=True))
    op.add_column('house_plans', sa.Column('construction_complexity', sa.String(length=30), nullable=True))
    op.add_column('house_plans', sa.Column('estimated_construction_cost_note', sa.String(length=300), nullable=True))
    op.add_column('house_plans', sa.Column('suitable_climate', sa.String(length=200), nullable=True))
    op.add_column('house_plans', sa.Column('ideal_for', sa.String(length=200), nullable=True))
    op.add_column('house_plans', sa.Column('main_features', sa.Text(), nullable=True))
    op.add_column('house_plans', sa.Column('room_details', sa.Text(), nullable=True))
    op.add_column('house_plans', sa.Column('construction_notes', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('house_plans', 'construction_notes')
    op.drop_column('house_plans', 'room_details')
    op.drop_column('house_plans', 'main_features')
    op.drop_column('house_plans', 'ideal_for')
    op.drop_column('house_plans', 'suitable_climate')
    op.drop_column('house_plans', 'estimated_construction_cost_note')
    op.drop_column('house_plans', 'construction_complexity')
    op.drop_column('house_plans', 'ceiling_height')
    op.drop_column('house_plans', 'parking_spaces')
    op.drop_column('house_plans', 'foundation_type')
    op.drop_column('house_plans', 'structure_type')
    op.drop_column('house_plans', 'roof_type')
    op.drop_column('house_plans', 'building_length')
    op.drop_column('house_plans', 'building_width')
    op.drop_column('house_plans', 'number_of_floors')
    op.drop_column('house_plans', 'number_of_bathrooms')
    op.drop_column('house_plans', 'number_of_bedrooms')
    op.drop_column('house_plans', 'total_area_sqft')
    op.drop_column('house_plans', 'total_area_m2')
