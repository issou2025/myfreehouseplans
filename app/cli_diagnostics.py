"""
Database Diagnostic Tool

Run this script to diagnose database connection and schema issues.
Usage: flask diagnose-db
"""

import click
from flask.cli import with_appcontext
from sqlalchemy import inspect, text
import sys


@click.command('diagnose-db')
@with_appcontext
def diagnose_db_command():
    """Comprehensive database diagnostics for troubleshooting."""
    from app.extensions import db
    from flask import current_app
    
    print("\n" + "="*70)
    print("🔍 DATABASE DIAGNOSTICS")
    print("="*70 + "\n")
    
    # 1. Configuration Check
    print("📋 Configuration:")
    print("-" * 70)
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if db_uri:
        # Sanitize password for display
        from urllib.parse import urlparse
        try:
            parsed = urlparse(db_uri)
            safe_uri = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port or 5432}{parsed.path}"
            print(f"  ✓ Database URI: {safe_uri}")
        except Exception:
            print(f"  ⚠ Database URI: <unable to parse>")
    else:
        print(f"  ❌ Database URI: NOT SET")
        print("\n💡 SOLUTION: Set DATABASE_URL environment variable\n")
        sys.exit(1)
    
    print(f"  ✓ Environment: {current_app.config.get('ENV', 'unknown')}")
    print(f"  ✓ Debug mode: {current_app.config.get('DEBUG', False)}")
    print()
    
    # 2. Connectivity Test
    print("🔌 Connectivity Test:")
    print("-" * 70)
    try:
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        print("  ✓ Database connection successful")
    except Exception as exc:
        print(f"  ❌ Database connection FAILED: {exc}")
        print("\n💡 SOLUTION:")
        print("  1. Verify DATABASE_URL is correct")
        print("  2. Check if database server is running")
        print("  3. Verify network connectivity")
        print("  4. Check firewall rules\n")
        sys.exit(1)
    print()
    
    # 3. Database Version
    print("📦 Database Information:")
    print("-" * 70)
    try:
        result = db.session.execute(text('SELECT version()'))
        version = result.fetchone()[0]
        print(f"  ✓ PostgreSQL version: {version.split(',')[0]}")
    except Exception as exc:
        print(f"  ⚠ Could not get database version: {exc}")
    print()
    
    # 4. Schema Inspection
    print("🗄️  Schema Inspection:")
    print("-" * 70)
    try:
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        
        # Import models to get expected tables
        import app.models  # noqa: F401
        required_tables = set(db.metadata.tables.keys())
        
        print(f"  ✓ Existing tables: {len(existing_tables)}")
        for table in sorted(existing_tables):
            print(f"    • {table}")
        
        print(f"\n  ✓ Required tables: {len(required_tables)}")
        for table in sorted(required_tables):
            exists = table in existing_tables
            symbol = "✓" if exists else "❌"
            print(f"    {symbol} {table}")
        
        missing = required_tables - existing_tables
        if missing:
            print(f"\n  ❌ Missing tables: {', '.join(sorted(missing))}")
            print("\n💡 SOLUTION:")
            print("  Run: flask db upgrade")
            print("  Or in Render: Add to render.yaml:")
            print("    releaseCommand: flask db upgrade\n")
        else:
            print("\n  ✓ All required tables exist")
    except Exception as exc:
        print(f"  ❌ Schema inspection failed: {exc}")
        import traceback
        traceback.print_exc()
    print()
    
    # 5. Migration Status
    print("🔄 Migration Status:")
    print("-" * 70)
    try:
        # Check if alembic_version table exists
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'alembic_version' in tables:
            result = db.session.execute(text('SELECT version_num FROM alembic_version'))
            row = result.fetchone()
            if row:
                print(f"  ✓ Current revision: {row[0]}")
            else:
                print("  ⚠ alembic_version table exists but is empty")
                print("\n💡 SOLUTION:")
                print("  Run: flask db stamp head\n")
        else:
            print("  ⚠ alembic_version table does not exist")
            print("  This means migrations have never been run")
            print("\n💡 SOLUTION:")
            print("  Run: flask db upgrade\n")
    except Exception as exc:
        print(f"  ⚠ Could not check migration status: {exc}")
    print()
    
    # 6. Connection Pool Status
    print("🏊 Connection Pool:")
    print("-" * 70)
    try:
        pool = db.engine.pool
        print(f"  ✓ Pool size: {pool.size()}")
        print(f"  ✓ Checked out connections: {pool.checkedout()}")
        print(f"  ✓ Overflow: {pool.overflow()}")
    except Exception as exc:
        print(f"  ⚠ Could not get pool status: {exc}")
    print()
    
    # 7. Test Write
    print("✍️  Write Test:")
    print("-" * 70)
    try:
        # Try to create a temporary table
        db.session.execute(text('''
            CREATE TEMPORARY TABLE test_write_permissions (
                id SERIAL PRIMARY KEY,
                test_data VARCHAR(100)
            )
        '''))
        db.session.execute(text("INSERT INTO test_write_permissions (test_data) VALUES ('test')"))
        db.session.commit()
        print("  ✓ Write permissions confirmed")
    except Exception as exc:
        print(f"  ❌ Write test FAILED: {exc}")
        print("\n💡 SOLUTION:")
        print("  Check database user permissions")
        print("  User needs CREATE, INSERT, UPDATE, DELETE privileges\n")
    print()
    
    print("="*70)
    print("✅ Diagnostics complete")
    print("="*70 + "\n")
