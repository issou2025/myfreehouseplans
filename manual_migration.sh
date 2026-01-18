#!/bin/bash
# Manual migration script for Render Shell
# Use this if automatic migration via releaseCommand doesn't work

echo "🔍 Checking current migration status..."
flask db current

echo ""
echo "📋 Available migrations:"
flask db history

echo ""
echo "🚀 Running migration upgrade..."
flask db upgrade

echo ""
echo "✅ Verifying blog_posts table exists..."
python -c "
from app import create_app
from app.models import BlogPost
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(app.extensions['sqlalchemy'].engine)
    tables = inspector.get_table_names()
    
    if 'blog_posts' in tables:
        print('✅ blog_posts table EXISTS')
        columns = [col['name'] for col in inspector.get_columns('blog_posts')]
        print(f'   Columns: {columns}')
        
        # Test query
        count = BlogPost.query.count()
        print(f'   BlogPost count: {count}')
    else:
        print('❌ blog_posts table DOES NOT EXIST')
        print(f'   Available tables: {tables}')
"

echo ""
echo "🎯 Current migration status:"
flask db current
