"""Add plan pack fields and SEO columns

Revision ID: 0001_add_plan_packs
Revises: 
Create Date: 2026-01-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_add_plan_packs'
down_revision = '0000_initial'
branch_labels = None
depends_on = None


def upgrade():
    # Add pack pricing columns
    op.add_column('house_plans', sa.Column('price_pack_2', sa.Numeric(10,2), nullable=True))
    op.add_column('house_plans', sa.Column('price_pack_3', sa.Numeric(10,2), nullable=True))

    # Add file columns
    op.add_column('house_plans', sa.Column('free_pdf_file', sa.String(length=300), nullable=True))
    op.add_column('house_plans', sa.Column('zip_pack_2', sa.String(length=300), nullable=True))
    op.add_column('house_plans', sa.Column('zip_pack_3', sa.String(length=300), nullable=True))
    op.add_column('house_plans', sa.Column('cover_image', sa.String(length=300), nullable=True))

    # Add SEO columns
    op.add_column('house_plans', sa.Column('seo_title', sa.String(length=200), nullable=True))
    op.add_column('house_plans', sa.Column('seo_description', sa.String(length=300), nullable=True))
    op.add_column('house_plans', sa.Column('seo_keywords', sa.String(length=300), nullable=True))


def downgrade():
    op.drop_column('house_plans', 'seo_keywords')
    op.drop_column('house_plans', 'seo_description')
    op.drop_column('house_plans', 'seo_title')

    op.drop_column('house_plans', 'cover_image')
    op.drop_column('house_plans', 'zip_pack_3')
    op.drop_column('house_plans', 'zip_pack_2')
    op.drop_column('house_plans', 'free_pdf_file')

    op.drop_column('house_plans', 'price_pack_3')
    op.drop_column('house_plans', 'price_pack_2')
