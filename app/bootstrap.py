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
    """
    Verify database schema integrity at application startup.
    
    This function performs read-only checks to ensure all required tables exist.
    It does NOT create, modify, or seed any data.
    
    For admin account management, use: flask create-admin or flask reset-admin-password
    """
    if os.environ.get('SKIP_STARTUP_DB_TASKS') == '1':
        app.logger.warning('Skipping startup DB checks due to SKIP_STARTUP_DB_TASKS=1')
        return

    with app.app_context():
        try:
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
            
            current_app.logger.info('Database schema validation passed (%d tables)', len(required))
        except Exception as exc:
            current_app.logger.error('Database readiness check failed: %s', exc)
            raise

        current_app.logger.info('Admin credentials synchronized with environment variables.')
