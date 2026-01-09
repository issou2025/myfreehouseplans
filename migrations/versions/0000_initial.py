"""Initial schema

Revision ID: 0000_initial
Revises:
Create Date: 2026-01-08

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0000_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('first_name', sa.String(length=100)),
        sa.Column('last_name', sa.String(length=100)),
        sa.Column('is_admin', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('username', name='uq_users_username'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=False)
    op.create_index('ix_users_email', 'users', ['email'], unique=False)

    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('name', name='uq_categories_name'),
        sa.UniqueConstraint('slug', name='uq_categories_slug'),
    )
    op.create_index('ix_categories_slug', 'categories', ['slug'], unique=False)

    op.create_table(
        'house_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=250), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('short_description', sa.String(length=300)),

        # Plan specifications
        sa.Column('bedrooms', sa.Integer()),
        sa.Column('bathrooms', sa.Float()),
        sa.Column('square_feet', sa.Integer()),
        sa.Column('stories', sa.Integer(), nullable=True),
        sa.Column('garage', sa.Integer(), nullable=True),

        # Pricing
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('sale_price', sa.Numeric(10, 2)),

        # Media (legacy/current)
        sa.Column('main_image', sa.String(length=300)),
        sa.Column('floor_plan_image', sa.String(length=300)),
        sa.Column('pdf_file', sa.String(length=300)),

        # Status
        sa.Column('is_featured', sa.Boolean(), nullable=True),
        sa.Column('is_published', sa.Boolean(), nullable=True),
        sa.Column('views_count', sa.Integer(), nullable=True),

        # Relationships
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id')),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),

        sa.UniqueConstraint('slug', name='uq_house_plans_slug'),
    )
    op.create_index('ix_house_plans_slug', 'house_plans', ['slug'], unique=False)

    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_number', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('house_plans.id'), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('payment_method', sa.String(length=50)),
        sa.Column('payment_status', sa.String(length=50), nullable=True),
        sa.Column('transaction_id', sa.String(length=200)),
        sa.Column('billing_email', sa.String(length=120), nullable=False),
        sa.Column('billing_name', sa.String(length=200)),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime()),
        sa.UniqueConstraint('order_number', name='uq_orders_order_number'),
    )
    op.create_index('ix_orders_order_number', 'orders', ['order_number'], unique=False)


def downgrade():
    op.drop_index('ix_orders_order_number', table_name='orders')
    op.drop_table('orders')

    op.drop_index('ix_house_plans_slug', table_name='house_plans')
    op.drop_table('house_plans')

    op.drop_index('ix_categories_slug', table_name='categories')
    op.drop_table('categories')

    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')
