"""Add visitor tracking table

Revision ID: 0008_visitor_tracking
Revises: 0007_plan_editorial_depth_fields
Create Date: 2026-01-09

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0008_visitor_tracking'
down_revision = '0007_plan_editorial_depth_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'visitors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('visit_date', sa.Date(), nullable=False),
        sa.Column('visitor_name', sa.String(length=120), nullable=True),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=False),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('page_visited', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_visitors_visit_date', 'visitors', ['visit_date'])
    op.create_index('ix_visitors_page_visited', 'visitors', ['page_visited'])
    op.create_index('ix_visitors_created_at', 'visitors', ['created_at'])


def downgrade():
    op.drop_index('ix_visitors_created_at', table_name='visitors')
    op.drop_index('ix_visitors_page_visited', table_name='visitors')
    op.drop_index('ix_visitors_visit_date', table_name='visitors')
    op.drop_table('visitors')
