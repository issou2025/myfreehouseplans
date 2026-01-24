"""smart analytics

Revision ID: 0015_smart_analytics
Revises: 0014_add_blog_posts_table
Create Date: 2026-01-25

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015_smart_analytics'
down_revision = '0014_add_blog_posts_table'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'daily_traffic_stats',
        sa.Column('date', sa.Date(), primary_key=True, nullable=False),
        sa.Column('human_visits', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('bot_visits', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('blocked_attacks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('revenue', sa.Float(), nullable=False, server_default='0'),
        sa.Column('top_countries', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_daily_traffic_stats_date', 'daily_traffic_stats', ['date'], unique=False)

    op.create_table(
        'recent_logs',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=False),
        sa.Column('country_code', sa.String(length=8), nullable=True),
        sa.Column('country_name', sa.String(length=80), nullable=True),
        sa.Column('request_path', sa.String(length=255), nullable=False),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('traffic_type', sa.String(length=16), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_recent_logs_ip_address', 'recent_logs', ['ip_address'], unique=False)
    op.create_index('ix_recent_logs_request_path', 'recent_logs', ['request_path'], unique=False)
    op.create_index('ix_recent_logs_traffic_type', 'recent_logs', ['traffic_type'], unique=False)
    op.create_index('ix_recent_logs_timestamp', 'recent_logs', ['timestamp'], unique=False)
    op.create_index('ix_recent_logs_type_time', 'recent_logs', ['traffic_type', 'timestamp'], unique=False)


def downgrade():
    op.drop_index('ix_recent_logs_type_time', table_name='recent_logs')
    op.drop_index('ix_recent_logs_timestamp', table_name='recent_logs')
    op.drop_index('ix_recent_logs_traffic_type', table_name='recent_logs')
    op.drop_index('ix_recent_logs_request_path', table_name='recent_logs')
    op.drop_index('ix_recent_logs_ip_address', table_name='recent_logs')
    op.drop_table('recent_logs')

    op.drop_index('ix_daily_traffic_stats_date', table_name='daily_traffic_stats')
    op.drop_table('daily_traffic_stats')
