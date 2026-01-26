"""
Database initialization with intelligent fallback strategy.

ARCHITECTURAL PHILOSOPHY:
-----------------------
Production applications should ALWAYS use migrations (Alembic) for schema management.
This module provides a FALLBACK mechanism for development environments where migrations
may not have been run yet, but it NEVER bypasses migrations in production.

PRIORITY ORDER:
1. Migrations (flask db upgrade) - ALWAYS preferred
2. Schema validation - Verify tables exist
3. Emergency fallback (db.create_all) - ONLY in development, ONLY if tables missing

NEVER use db.create_all() as a primary schema management strategy.
"""

import os
from flask import current_app
from sqlalchemy import inspect, text
from app.extensions import db


def get_missing_tables() -> set:
    """
    Inspect database and return set of tables that should exist but don't.
    
    This compares SQLAlchemy metadata (defined models) against actual database
    tables, identifying gaps without attempting any modifications.
    """
    try:
        # Import models to populate metadata
        import app.models  # noqa: F401
        
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        required_tables = set(db.metadata.tables.keys())
        
        missing = required_tables - existing_tables
        return missing
    except Exception as exc:
        current_app.logger.error(
            'Failed to inspect database tables: %s',
            exc,
            exc_info=True
        )
        return set()


def get_missing_columns_by_table() -> dict[str, list[str]]:
    """Return missing columns for each existing model table.

    Compares SQLAlchemy metadata (models) with the live database schema.
    This is non-destructive and intended for diagnostics/logging.
    """
    try:
        # Import models to populate metadata
        import app.models  # noqa: F401

        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

        missing_by_table: dict[str, list[str]] = {}
        for table_name, table in db.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            expected_cols = {c.name for c in table.columns}
            actual_cols = {c['name'] for c in inspector.get_columns(table_name)}
            missing_cols = sorted(expected_cols - actual_cols)
            if missing_cols:
                missing_by_table[table_name] = missing_cols
        return missing_by_table
    except Exception as exc:
        current_app.logger.error(
            'Failed to inspect database columns: %s',
            exc,
            exc_info=True,
        )
        return {}


def verify_alembic_version_table() -> bool:
    """
    Check if alembic_version table exists.
    
    Presence of this table indicates migrations have been initialized.
    If this table exists, we MUST use migrations, never db.create_all().
    """
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        return 'alembic_version' in tables
    except Exception as exc:
        current_app.logger.error(
            'Failed to check alembic_version table: %s',
            exc,
            exc_info=True
        )
        return False


def get_alembic_current_revision() -> str | None:
    """
    Get the current Alembic revision from the database.
    
    Returns None if alembic_version table doesn't exist or is empty.
    """
    try:
        result = db.session.execute(
            text('SELECT version_num FROM alembic_version LIMIT 1')
        )
        row = result.fetchone()
        return row[0] if row else None
    except Exception:
        return None


def emergency_create_schema(app) -> bool:
    """
    EMERGENCY FALLBACK: Create schema using db.create_all().
    
    THIS IS A LAST RESORT and should ONLY run when:
    1. We're in development (not production)
    2. No alembic_version table exists (migrations never run)
    3. Required tables are missing
    
    CRITICAL WARNINGS:
    - This bypasses migration versioning
    - This cannot update existing tables
    - This is NOT a substitute for proper migrations
    - This should NEVER run in production
    
    Returns True if schema was created, False otherwise.
    """
    config_name = app.config.get('ENV', 'production')
    
    # ABSOLUTE PROHIBITION: Never run in production
    if config_name == 'production':
        current_app.logger.error(
            'FATAL: emergency_create_schema() called in production. '
            'This is a critical misconfiguration. Use flask db upgrade instead.'
        )
        return False
    
    # Check if migrations are initialized
    has_alembic = verify_alembic_version_table()
    if has_alembic:
        current_app.logger.error(
            'FATAL: Alembic version table exists but tables are missing. '
            'This indicates a broken migration state. '
            'Run: flask db upgrade'
        )
        return False
    
    missing_tables = get_missing_tables()
    if not missing_tables:
        current_app.logger.info('All required tables exist. No schema creation needed.')
        return True
    
    current_app.logger.warning(
        'EMERGENCY FALLBACK ACTIVATED: Creating schema with db.create_all(). '
        'Missing tables: %s. This should ONLY happen in local development. '
        'For production, use: flask db upgrade',
        ', '.join(sorted(missing_tables))
    )
    
    try:
        db.create_all()
        current_app.logger.info(
            'Emergency schema creation completed. '
            'IMPORTANT: Initialize migrations with: flask db stamp head'
        )
        return True
    except Exception as exc:
        current_app.logger.error(
            'FATAL: Emergency schema creation failed: %s',
            exc,
            exc_info=True
        )
        return False


def intelligent_db_init(app) -> None:
    """
    Intelligent database initialization with proper error handling.
    
    STRATEGY:
    1. Test database connectivity
    2. Verify required tables exist
    3. If in production and tables missing -> FAIL FAST with clear error
    4. If in development and tables missing -> Provide guidance or fallback
    
    This function is called during app factory initialization.
    """
    # Skip if explicitly disabled
    if os.environ.get('SKIP_DB_INIT') == '1':
        current_app.logger.info('Database initialization skipped (SKIP_DB_INIT=1)')
        return
    
    with app.app_context():
        # Test database connectivity
        try:
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            current_app.logger.info('✓ Database connectivity verified')
        except Exception as exc:
            current_app.logger.error(
                '✗ FATAL: Cannot connect to database: %s. '
                'Check DATABASE_URL environment variable.',
                exc,
                exc_info=True
            )
            raise RuntimeError(f'Database connection failed: {exc}') from exc
        
        # Check for missing tables
        missing_tables = get_missing_tables()
        
        if not missing_tables:
            current_app.logger.info('✓ All required database tables exist')

            # Log column drift (do not crash). Missing columns frequently
            # manifest as SQLAlchemy OperationalError (sqlalche.me/e/20/f405).
            missing_cols = get_missing_columns_by_table()
            if missing_cols:
                preview = ', '.join(
                    f"{t}({len(cols)})" for t, cols in sorted(missing_cols.items())
                )
                current_app.logger.warning(
                    '⚠ Database schema drift detected (missing columns). Tables affected: %s. '
                    'Run: flask db upgrade',
                    preview,
                )
                # Log a compact per-table list (kept short to avoid noisy logs).
                for table_name, cols in sorted(missing_cols.items()):
                    current_app.logger.warning('  - %s missing columns: %s', table_name, ', '.join(cols))
            
            # Verify alembic state if migrations are initialized
            if verify_alembic_version_table():
                revision = get_alembic_current_revision()
                if revision:
                    current_app.logger.info(f'✓ Alembic revision: {revision}')
                else:
                    current_app.logger.warning(
                        '⚠ Alembic version table exists but is empty. '
                        'Run: flask db stamp head'
                    )
            return
        
        # Tables are missing - handle based on environment
        config_name = app.config.get('ENV', 'production')
        
        if config_name == 'production':
            # PRODUCTION: Fail fast with clear instructions
            error_msg = (
                f"FATAL: Missing database tables in production: {', '.join(sorted(missing_tables))}. "
                "This indicates migrations were not run during deployment. "
                "SOLUTION: Ensure render.yaml contains: "
                "releaseCommand: flask db upgrade"
            )
            current_app.logger.error(error_msg)
            raise RuntimeError(error_msg)
        else:
            # DEVELOPMENT: Attempt emergency fallback
            current_app.logger.warning(
                '⚠ Missing tables in development environment: %s. '
                'Attempting emergency fallback.',
                ', '.join(sorted(missing_tables))
            )
            
            success = emergency_create_schema(app)
            if not success:
                raise RuntimeError(
                    'Failed to create database schema. '
                    'Run: flask db upgrade'
                )
