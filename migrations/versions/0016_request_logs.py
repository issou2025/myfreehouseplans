"""request logs tables and recent log metadata

Revision ID: 0016_request_logs
Revises: 0015_smart_analytics
Create Date: 2026-01-25

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0016_request_logs'
down_revision = '0015_smart_analytics'
branch_labels = None
depends_on = None


def _create_request_log_table(table_name: str, with_analyzer_fields: bool = False, with_error_fields: bool = False):
    columns = [
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('ip_address', sa.String(length=64), nullable=False),
        sa.Column('route', sa.String(length=255), nullable=False),
        sa.Column('method', sa.String(length=12), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_time_ms', sa.Float(), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('device', sa.String(length=32), nullable=True),
        sa.Column('country', sa.String(length=80), nullable=True),
        sa.Column('referrer', sa.String(length=500), nullable=True),
        sa.Column('session_id', sa.String(length=120), nullable=True),
    ]

    if with_analyzer_fields:
        columns.extend([
            sa.Column('event_type', sa.String(length=40), nullable=True),
            sa.Column('detail', sa.String(length=800), nullable=True),
        ])

    if with_error_fields:
        columns.extend([
            sa.Column('error_type', sa.String(length=120), nullable=True),
            sa.Column('error_message', sa.String(length=1000), nullable=True),
            sa.Column('stacktrace', sa.Text(), nullable=True),
        ])

    op.create_table(table_name, *columns)
    op.create_index(f'ix_{table_name}_timestamp', table_name, ['timestamp'], unique=False)
    op.create_index(f'ix_{table_name}_ip_address', table_name, ['ip_address'], unique=False)
    op.create_index(f'ix_{table_name}_route', table_name, ['route'], unique=False)


def upgrade():
    # Extend recent_logs with richer metadata
    op.add_column('recent_logs', sa.Column('device', sa.String(length=32), nullable=True))
    op.add_column('recent_logs', sa.Column('method', sa.String(length=12), nullable=True))
    op.add_column('recent_logs', sa.Column('status_code', sa.Integer(), nullable=True))
    op.add_column('recent_logs', sa.Column('response_time_ms', sa.Float(), nullable=True))
    op.add_column('recent_logs', sa.Column('referrer', sa.String(length=500), nullable=True))
    op.add_column('recent_logs', sa.Column('session_id', sa.String(length=120), nullable=True))
    op.add_column('recent_logs', sa.Column('is_search_bot', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index('ix_recent_logs_session_id', 'recent_logs', ['session_id'], unique=False)

    _create_request_log_table('visitor_logs')
    _create_request_log_table('crawler_logs')
    _create_request_log_table('bot_logs')
    _create_request_log_table('api_logs')
    _create_request_log_table('performance_logs')
    _create_request_log_table('analyzer_logs', with_analyzer_fields=True)
    _create_request_log_table('error_logs', with_error_fields=True)


def downgrade():
    for table in ('error_logs', 'analyzer_logs', 'performance_logs', 'api_logs', 'bot_logs', 'crawler_logs', 'visitor_logs'):
        op.drop_index(f'ix_{table}_route', table_name=table)
        op.drop_index(f'ix_{table}_ip_address', table_name=table)
        op.drop_index(f'ix_{table}_timestamp', table_name=table)
        op.drop_table(table)

    op.drop_index('ix_recent_logs_session_id', table_name='recent_logs')
    op.drop_column('recent_logs', 'is_search_bot')
    op.drop_column('recent_logs', 'session_id')
    op.drop_column('recent_logs', 'referrer')
    op.drop_column('recent_logs', 'response_time_ms')
    op.drop_column('recent_logs', 'status_code')
    op.drop_column('recent_logs', 'method')
    op.drop_column('recent_logs', 'device')
