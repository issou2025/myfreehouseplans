import os
from typing import List
import importlib

from flask import current_app
from sqlalchemy import inspect

from app.extensions import db


REQUIRED_TABLES: List[str] = []


def _load_required_tables() -> List[str]:
    global REQUIRED_TABLES
    if REQUIRED_TABLES:
        return REQUIRED_TABLES
    if not db.metadata.tables:
        importlib.import_module('app.models')
    REQUIRED_TABLES = sorted({table.name for table in db.metadata.sorted_tables})
    return REQUIRED_TABLES


def ensure_database_ready(app) -> None:
    if os.environ.get('SKIP_STARTUP_DB_TASKS') == '1':
        app.logger.warning('Skipping startup DB checks due to SKIP_STARTUP_DB_TASKS=1')
        return

    with app.app_context():
        inspector = inspect(db.engine)
        existing = set(inspector.get_table_names())
        required = _load_required_tables()
        missing = [table for table in required if table not in existing]
        if missing:
            msg = (
                "Database schema is incomplete. Missing tables: "
                + ', '.join(missing)
                + ". Run 'flask db upgrade' before starting the app."
            )
            current_app.logger.error(msg)
            raise RuntimeError(msg)

        _ensure_admin_account()


def _ensure_admin_account() -> None:
    from app.models import User  # Local import to avoid circular dependency

    username = (os.environ.get('ADMIN_USERNAME') or '').strip()
    email = (os.environ.get('ADMIN_EMAIL') or '').strip()
    password = os.environ.get('ADMIN_PASSWORD')

    admin = User.query.filter_by(role='superadmin').first()

    if admin:
        _sync_admin_credentials(admin, username, email, password)
        return

    missing = [name for name, value in {
        'ADMIN_USERNAME': username,
        'ADMIN_EMAIL': email,
        'ADMIN_PASSWORD': password,
    }.items() if not value]
    if missing:
        msg = (
            'Admin account missing and the following env vars are empty: '
            + ', '.join(missing)
        )
        current_app.logger.error(msg)
        raise RuntimeError(msg)

    new_admin = User(
        username=username,
        email=email,
        role='superadmin',
        is_active=True,
    )
    new_admin.set_password(password)
    db.session.add(new_admin)
    db.session.commit()
    current_app.logger.info("Bootstrapped admin account '%s'", username)


def _sync_admin_credentials(admin, username, email, password) -> None:
    updated = False

    if username and admin.username != username:
        admin.username = username
        updated = True

    if email and admin.email != email:
        admin.email = email
        updated = True

    if password and not admin.check_password(password):
        admin.set_password(password)
        updated = True

    if updated:
        db.session.commit()
        current_app.logger.info('Admin credentials synchronized with environment variables.')
