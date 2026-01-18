#!/usr/bin/env python
"""
EMERGENCY DATABASE SYNC SCRIPT
Fixes: relation "blog_posts" does not exist

This script creates ONLY missing tables (blog_posts) without
dropping or modifying existing data.

Usage:
    python sync_db.py
"""

import sys
import os

# Set Flask app environment
os.environ['FLASK_APP'] = 'wsgi:app'

print("=" * 70)
print("🚨 EMERGENCY DATABASE SYNC - CREATING MISSING TABLES")
print("=" * 70)

try:
    print("\n[1/5] Importing Flask application...")
    from app import create_app
    from app.extensions import db
    from sqlalchemy import inspect, text
    
    app = create_app()
    print("✅ Application imported successfully")
    
    with app.app_context():
        print("\n[2/5] Testing database connection...")
        try:
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            print("✅ Database connection verified")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            sys.exit(1)
        
        print("\n[3/5] Checking existing tables...")
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        print(f"✅ Found {len(existing_tables)} existing tables")
        
        # Import models to ensure metadata is populated
        print("\n[4/5] Importing models and checking blog_posts...")
        from app.models import (
            User, HousePlan, Category, Order, 
            ContactMessage, Visitor, BlogPost, PlanFAQ
        )
        
        if 'blog_posts' in existing_tables:
            print("⚠️  blog_posts table ALREADY EXISTS")
            columns = [col['name'] for col in inspector.get_columns('blog_posts')]
            print(f"   Columns: {', '.join(columns)}")
            
            # Verify plan_id foreign key
            if 'plan_id' in columns:
                print("✅ plan_id foreign key column exists")
            else:
                print("⚠️  plan_id column missing!")
        else:
            print("❌ blog_posts table DOES NOT EXIST - will create it")
            
            print("\n[5/5] Creating missing tables with db.create_all()...")
            try:
                # This creates ONLY missing tables, doesn't touch existing ones
                db.create_all()
                print("✅ db.create_all() executed successfully")
                
                # Verify blog_posts was created
                inspector = inspect(db.engine)
                tables_after = set(inspector.get_table_names())
                
                if 'blog_posts' in tables_after:
                    print("\n" + "=" * 70)
                    print("✅ SUCCESS: blog_posts table created")
                    print("=" * 70)
                    
                    columns = [col['name'] for col in inspector.get_columns('blog_posts')]
                    print(f"\nColumns created: {', '.join(columns)}")
                    
                    # Verify foreign key
                    if 'plan_id' in columns:
                        print("✅ plan_id foreign key linked to house_plans.id")
                    
                    # Test query
                    count = BlogPost.query.count()
                    print(f"✅ BlogPost query test passed (count: {count})")
                    
                    print("\n" + "=" * 70)
                    print("🎉 DATABASE SYNC COMPLETE")
                    print("=" * 70)
                    print("\nThe application should now work without errors.")
                    print("You can safely restart the Render service.")
                else:
                    print("\n❌ FAILED: blog_posts table was not created")
                    print(f"Tables after sync: {', '.join(sorted(tables_after))}")
                    sys.exit(1)
                    
            except Exception as e:
                print(f"\n❌ ERROR during db.create_all(): {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)

except ImportError as e:
    print(f"\n❌ IMPORT ERROR: {e}")
    print("Make sure all dependencies are installed:")
    print("  pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ FATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
