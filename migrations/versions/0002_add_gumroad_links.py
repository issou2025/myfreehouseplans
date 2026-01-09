"""Add Gumroad links to house plans

Revision ID: 0002_add_gumroad_links
Revises: 0001_add_plan_packs
Create Date: 2026-01-09

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_gumroad_links'
down_revision = '0001_add_plan_packs'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('house_plans', sa.Column('gumroad_pack_2_url', sa.String(length=500), nullable=True))
    op.add_column('house_plans', sa.Column('gumroad_pack_3_url', sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column('house_plans', 'gumroad_pack_3_url')
    op.drop_column('house_plans', 'gumroad_pack_2_url')
