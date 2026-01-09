"""Create contact messages inbox table

Revision ID: 0006_contact_messages_inbox
Revises: 0005_plan_pricing_reference_codes
Create Date: 2026-01-09

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_contact_messages_inbox'
down_revision = '0005_plan_pricing_reference_codes'
branch_labels = None
depends_on = None


STATUS_DEFAULT = 'new'
EMAIL_STATUS_DEFAULT = 'pending'


def upgrade():
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=False),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('inquiry_type', sa.String(length=40), nullable=False),
        sa.Column('reference_code', sa.String(length=60), nullable=True),
        sa.Column('subscribe', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('plan_id', sa.Integer(), nullable=True),
        sa.Column('plan_snapshot', sa.String(length=255), nullable=True),
        sa.Column('attachment_path', sa.String(length=300), nullable=True),
        sa.Column('attachment_name', sa.String(length=255), nullable=True),
        sa.Column('attachment_mime', sa.String(length=120), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text(f"'{STATUS_DEFAULT}'")),
        sa.Column('status_updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('email_status', sa.String(length=20), nullable=False, server_default=sa.text(f"'{EMAIL_STATUS_DEFAULT}'")),
        sa.Column('email_error', sa.Text(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['house_plans.id'], name='fk_messages_plan_id', ondelete='SET NULL'),
    )

    op.create_index('ix_messages_email', 'messages', ['email'])
    op.create_index('ix_messages_created_at', 'messages', ['created_at'])
    op.create_index('ix_messages_status', 'messages', ['status'])
    op.create_index('ix_messages_status_created', 'messages', ['status', 'created_at'])


def downgrade():
    op.drop_index('ix_messages_status_created', table_name='messages')
    op.drop_index('ix_messages_status', table_name='messages')
    op.drop_index('ix_messages_created_at', table_name='messages')
    op.drop_index('ix_messages_email', table_name='messages')
    op.drop_table('messages')
