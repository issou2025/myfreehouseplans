"""Safe startup schema patch (non-destructive).

This runner intentionally avoids db.create_all() and NEVER drops tables.
Instead, it performs a minimal, targeted schema patch for critical columns
that have caused production issues:

- users.role
- house_plans.created_by_id

If missing, columns are added using ALTER TABLE.
It also backfills created_by_id for existing plans so they are visible.
"""

import os

from sqlalchemy import inspect, text

from wsgi import app
from app.extensions import db


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(db.engine)
    try:
        cols = inspector.get_columns(table_name)
    except Exception:
        return False
    return any(c.get('name') == column_name for c in cols)


def _table_exists(table_name: str) -> bool:
    inspector = inspect(db.engine)
    try:
        return table_name in set(inspector.get_table_names())
    except Exception:
        return False


def _ensure_columns_and_backfill() -> None:
    """Add missing columns safely and backfill plan ownership."""

    # Import models to ensure metadata is available (and relationships are defined)
    import app.models  # noqa: F401

    dialect = getattr(db.engine.dialect, 'name', '')

    # 1) Ensure users.role exists
    if _table_exists('users') and not _has_column('users', 'role'):
        if dialect == 'postgresql':
            db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50)"))
        else:
            db.session.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(50)"))
        # Backfill: make id=1 the owner admin if present; others default to customer
        db.session.execute(text("UPDATE users SET role='superadmin' WHERE id=1 AND (role IS NULL OR role='')"))
        db.session.execute(text("UPDATE users SET role='customer' WHERE role IS NULL OR role=''"))

    # 2) Ensure house_plans.created_by_id exists
    if _table_exists('house_plans') and not _has_column('house_plans', 'created_by_id'):
        if dialect == 'postgresql':
            db.session.execute(text("ALTER TABLE house_plans ADD COLUMN IF NOT EXISTS created_by_id INTEGER"))
        else:
            db.session.execute(text("ALTER TABLE house_plans ADD COLUMN created_by_id INTEGER"))
        # Index helps admin/staff filtering.
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_house_plans_created_by_id ON house_plans (created_by_id)"))

    # 3) Backfill created_by_id for existing plans
    if _table_exists('house_plans') and _has_column('house_plans', 'created_by_id'):
        # Prefer admin id=1 when it exists.
        admin_id = db.session.execute(text("SELECT id FROM users WHERE id=1")).scalar()
        if not admin_id:
            admin_id = db.session.execute(text("SELECT id FROM users WHERE role='superadmin' ORDER BY id ASC LIMIT 1")).scalar()
        if admin_id:
            db.session.execute(
                text("UPDATE house_plans SET created_by_id = :admin_id WHERE created_by_id IS NULL"),
                {'admin_id': int(admin_id)},
            )

    db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        _ensure_columns_and_backfill()

    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    app.run(host=host, port=port)