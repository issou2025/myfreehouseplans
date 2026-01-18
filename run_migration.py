#!/usr/bin/env python
"""
Manual Migration Runner for Render
Run this in Render Shell if automatic migration fails
"""

import sys
import os

# Set Flask app
os.environ['FLASK_APP'] = 'wsgi:app'

print("=" * 60)
print("🔧 MANUAL MIGRATION RUNNER")
print("=" * 60)

try:
    from app import create_app
    from app.extensions import db
    from flask_migrate import upgrade, current, stamp
    from sqlalchemy import inspect, text
    
    app = create_app()
    
    with app.app_context():
        print("\n1️⃣ Checking database connection...")
        try:
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            print("   ✅ Database connected")
        except Exception as e:
            print(f"   ❌ Connection failed: {e}")
            sys.exit(1)
        
        print("\n2️⃣ Checking current migration status...")
        try:
            from alembic.migration import MigrationContext
            from alembic.config import Config
            
            conn = db.engine.connect()
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            
            if current_rev:
                print(f"   Current revision: {current_rev}")
            else:
                print("   No migrations applied yet")
        except Exception as e:
            print(f"   ⚠️  Could not check status: {e}")
        
        print("\n3️⃣ Checking if blog_posts table exists...")
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'blog_posts' in tables:
            print("   ✅ blog_posts table already exists")
            columns = [col['name'] for col in inspector.get_columns('blog_posts')]
            print(f"   Columns: {', '.join(columns)}")
        else:
            print("   ❌ blog_posts table DOES NOT exist")
            print(f"   Available tables: {', '.join(sorted(tables))}")
        
        if 'blog_posts' not in tables:
            print("\n4️⃣ Running flask db upgrade...")
            try:
                upgrade()
                print("   ✅ Migration completed successfully")
            except Exception as e:
                print(f"   ❌ Migration failed: {e}")
                print("\n   Attempting to stamp to latest revision...")
                try:
                    stamp('0013_add_plan_created_by')
                    print("   Stamped to 0013_add_plan_created_by")
                    print("   Retrying upgrade...")
                    upgrade()
                    print("   ✅ Migration completed on retry")
                except Exception as e2:
                    print(f"   ❌ Still failed: {e2}")
                    sys.exit(1)
        
        print("\n5️⃣ Final verification...")
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'blog_posts' in tables:
            print("   ✅ SUCCESS: blog_posts table exists")
            
            # Test query
            from app.models import BlogPost
            count = BlogPost.query.count()
            print(f"   BlogPost count: {count}")
            
            print("\n" + "=" * 60)
            print("✅ MIGRATION COMPLETE - DATABASE READY")
            print("=" * 60)
        else:
            print("   ❌ FAILED: blog_posts table still missing")
            sys.exit(1)

except Exception as e:
    print(f"\n❌ FATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
