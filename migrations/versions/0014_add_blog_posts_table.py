"""Add blog_posts table

Revision ID: 0014_add_blog_posts_table
Revises: 0013_add_plan_created_by
Create Date: 2026-01-18

CRITICAL FIX:
This migration creates the missing blog_posts table that was referenced
in models.py but never migrated to production. This table is required
for the BlogPost model and the HousePlan.blog_posts relationship.

SAFETY:
- This migration ONLY creates blog_posts table
- Does NOT touch any existing tables
- Safe to run on production with existing data
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '0014_add_blog_posts_table'
down_revision = '0013_add_plan_created_by'
branch_labels = None
depends_on = None


def upgrade():
    """Create blog_posts table with all required columns and indexes."""
    
    # Create ENUM type for blog_post_status (PostgreSQL)
    # For SQLite, this will be ignored and stored as TEXT
    blog_post_status_enum = postgresql.ENUM(
        'draft', 'published', 'archived',
        name='blog_post_status',
        create_type=False
    )
    
    # Try to create the enum type if it doesn't exist (PostgreSQL only)
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        connection.execute(sa.text(
            "DO $$ BEGIN "
            "CREATE TYPE blog_post_status AS ENUM ('draft', 'published', 'archived'); "
            "EXCEPTION WHEN duplicate_object THEN null; "
            "END $$;"
        ))
    
    # Create blog_posts table
    op.create_table(
        'blog_posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=200), nullable=False),
        sa.Column('meta_title', sa.String(length=150), nullable=True),
        sa.Column('meta_description', sa.String(length=160), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('cover_image', sa.String(length=600), nullable=True),
        sa.Column('plan_id', sa.Integer(), nullable=True),
        sa.Column(
            'status',
            blog_post_status_enum if connection.dialect.name == 'postgresql' else sa.String(20),
            nullable=False,
            server_default='draft'
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['plan_id'],
            ['house_plans.id'],
            name='fk_blog_posts_plan_id',
            ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id', name='pk_blog_posts'),
        sa.UniqueConstraint('slug', name='uq_blog_posts_slug')
    )
    
    # Create indexes for performance
    op.create_index('ix_blog_posts_slug', 'blog_posts', ['slug'], unique=True)
    op.create_index('ix_blog_posts_plan_id', 'blog_posts', ['plan_id'], unique=False)
    op.create_index('ix_blog_posts_status', 'blog_posts', ['status'], unique=False)


def downgrade():
    """Drop blog_posts table and enum type."""
    
    # Drop indexes first
    op.drop_index('ix_blog_posts_status', table_name='blog_posts')
    op.drop_index('ix_blog_posts_plan_id', table_name='blog_posts')
    op.drop_index('ix_blog_posts_slug', table_name='blog_posts')
    
    # Drop table
    op.drop_table('blog_posts')
    
    # Drop enum type (PostgreSQL only)
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        connection.execute(sa.text('DROP TYPE IF EXISTS blog_post_status;'))
