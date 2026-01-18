#!/usr/bin/env python3
"""
CRITICAL DATABASE RESTORATION SCRIPT
====================================
This script safely restores the missing 'blog_posts' table without touching existing data.

SAFETY GUARANTEES:
- NEVER calls db.drop_all()
- Only creates missing tables
- Preserves all existing data (house_plans, users, etc.)
- Uses db.create_all() which is safe for existing tables
"""

import sys
import traceback
from app import create_app
from app.extensions import db

def restore_database():
    """
    Safely restore missing database tables.
    
    This function uses db.create_all() which is safe because:
    - It only creates tables that don't exist
    - It skips existing tables without modification
    - It preserves all existing data
    """
    
    app = create_app()
    
    with app.app_context():
        try:
            print("🔄 Starting database restoration...")
            print("📋 Checking database state...")
            
            # Get current table names
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            print(f"📊 Found {len(existing_tables)} existing tables:")
            for table in sorted(existing_tables):
                print(f"   ✅ {table}")
            
            # Create missing tables (this is SAFE - only creates what's missing)
            print("\n🔧 Creating missing tables...")
            db.create_all()
            
            # Verify what was created
            updated_tables = db.inspect(db.engine).get_table_names()
            new_tables = set(updated_tables) - set(existing_tables)
            
            if new_tables:
                print(f"\n✨ Successfully created {len(new_tables)} new tables:")
                for table in sorted(new_tables):
                    print(f"   🆕 {table}")
            else:
                print("\n✅ All required tables already exist - no changes needed")
            
            print(f"\n📈 Total tables now: {len(updated_tables)}")
            
            # Verify blog_posts table specifically
            if 'blog_posts' in updated_tables:
                print("🎉 SUCCESS: blog_posts table is now available!")
                
                # Check blog_posts structure
                columns = inspector.get_columns('blog_posts')
                print(f"   📝 blog_posts has {len(columns)} columns:")
                for col in columns:
                    print(f"      - {col['name']} ({col['type']})")
                
            else:
                print("⚠️  WARNING: blog_posts table still missing")
                return False
            
            # Quick data integrity check
            try:
                from app.models import HousePlan, User, BlogPost
                
                house_plan_count = db.session.query(HousePlan).count()
                user_count = db.session.query(User).count()
                blog_count = db.session.query(BlogPost).count()
                
                print(f"\n📊 Data integrity check:")
                print(f"   🏠 House Plans: {house_plan_count}")
                print(f"   👥 Users: {user_count}")
                print(f"   📝 Blog Posts: {blog_count}")
                
            except Exception as e:
                print(f"⚠️  Could not verify data counts: {e}")
            
            print("\n🎯 DATABASE RESTORATION COMPLETE!")
            print("🚀 Your site should now be fully functional.")
            return True
            
        except Exception as e:
            print(f"\n❌ ERROR during restoration: {e}")
            print(f"🔍 Traceback:\n{traceback.format_exc()}")
            return False

if __name__ == '__main__':
    success = restore_database()
    if success:
        print("\n✅ Restoration completed successfully!")
        print("🌐 Your myfreehouseplans.com site is ready!")
        sys.exit(0)
    else:
        print("\n❌ Restoration failed!")
        print("📧 Contact support: entreprise2rc@gmail.com")
        sys.exit(1)