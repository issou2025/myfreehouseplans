"""Add tiered pricing and reference codes

Revision ID: 0005_plan_pricing_reference_codes
Revises: 0004_plan_categories_many_to_many
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime


def _coerce_datetime(value):
    """Best effort parsing for legacy string timestamps."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith('Z'):
            normalized = normalized[:-1]
        for pattern in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(normalized, pattern)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            pass
    return datetime.utcnow()


# revision identifiers, used by Alembic.
revision = '0005_plan_pricing_reference_codes'
down_revision = '0004_plan_categories_many_to_many'
branch_labels = None
depends_on = None


def _reference_code(sequence: int, created_at):
    """Return a stable reference code using the given sequence and year."""
    year = _coerce_datetime(created_at).year
    return f"MYFREEHOUSEPLANS-{sequence:04d}/{year}"


def upgrade():
    # Add new nullable columns with safe defaults first.
    with op.batch_alter_table('house_plans') as batch_op:
        batch_op.add_column(sa.Column('price_pack_1', sa.Numeric(10, 2), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('reference_code', sa.String(48), nullable=True))

    connection = op.get_bind()

    # Ensure pack 1 pricing mirrors the existing display price when missing.
    connection.execute(sa.text("""
        UPDATE house_plans
        SET price_pack_1 = COALESCE(price_pack_1, price, 0)
    """))

    # Build deterministic reference codes ordered by creation.
    plans = connection.execute(sa.text(
        """
        SELECT id, created_at
        FROM house_plans
        ORDER BY created_at ASC, id ASC
        """
    ))

    sequence = 1
    for plan in plans:
        code = _reference_code(sequence, plan.created_at)
        connection.execute(
            sa.text("UPDATE house_plans SET reference_code = :code WHERE id = :plan_id"),
            {"code": code, "plan_id": plan.id},
        )
        sequence += 1

    # Reference codes must now be unique and present.
    op.create_index('ix_house_plans_reference_code', 'house_plans', ['reference_code'], unique=True)

    with op.batch_alter_table('house_plans') as batch_op:
        batch_op.alter_column('reference_code', existing_type=sa.String(48), nullable=False)
        batch_op.alter_column('price_pack_1', existing_type=sa.Numeric(10, 2), nullable=False)


def downgrade():
    with op.batch_alter_table('house_plans') as batch_op:
        batch_op.alter_column('price_pack_1', existing_type=sa.Numeric(10, 2), nullable=True)
        batch_op.alter_column('reference_code', existing_type=sa.String(48), nullable=True)

    op.drop_index('ix_house_plans_reference_code', table_name='house_plans')

    with op.batch_alter_table('house_plans') as batch_op:
        batch_op.drop_column('reference_code')
        batch_op.drop_column('price_pack_1')
