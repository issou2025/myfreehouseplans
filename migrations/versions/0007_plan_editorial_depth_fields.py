"""Add plan editorial depth fields

Revision ID: 0007_plan_editorial_depth_fields
Revises: 0006_contact_messages_inbox
Create Date: 2026-01-09

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0007_plan_editorial_depth_fields'
down_revision = '0006_contact_messages_inbox'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('house_plans', sa.Column('plan_type', sa.String(length=40), nullable=True))
    op.add_column('house_plans', sa.Column('design_philosophy', sa.Text(), nullable=True))
    op.add_column('house_plans', sa.Column('lifestyle_suitability', sa.Text(), nullable=True))
    op.add_column('house_plans', sa.Column('customization_potential', sa.Text(), nullable=True))

    op.create_index('ix_house_plans_plan_type', 'house_plans', ['plan_type'])


def downgrade():
    op.drop_index('ix_house_plans_plan_type', table_name='house_plans')

    op.drop_column('house_plans', 'customization_potential')
    op.drop_column('house_plans', 'lifestyle_suitability')
    op.drop_column('house_plans', 'design_philosophy')
    op.drop_column('house_plans', 'plan_type')
