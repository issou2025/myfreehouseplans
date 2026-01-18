"""Safe production schema activation for Blog.

- Never drops tables
- Never deletes data
- Only creates missing tables via db.create_all()
- Verifies blog_posts exists
- Verifies FK blog_posts.plan_id -> house_plans.id exists
- Verifies BlogPost model has required columns
- Verifies admin blog endpoints are registered

Run on Render Shell:
  python fix_and_activate.py
"""

import os

from sqlalchemy import inspect

from app import create_app
from app.extensions import db


REQUIRED_BLOGPOST_COLUMNS = {
    'id',
    'title',
    'slug',
    'content',
    'plan_id',
    'created_at',
    'updated_at',
}


def _print_ok(msg: str) -> None:
    print(f"✓ {msg}")


def _print_warn(msg: str) -> None:
    print(f"⚠ {msg}")


def _print_fail(msg: str) -> None:
    print(f"✗ {msg}")


def main() -> int:
    config_name = os.getenv('FLASK_CONFIG') or os.getenv('FLASK_ENV') or 'production'
    app = create_app(config_name.lower())

    with app.app_context():
        # Ensure models are loaded
        from app.models import BlogPost  # noqa: F401

        # 1) Create missing tables safely
        db.create_all()
        _print_ok('db.create_all() executed (non-destructive)')

        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())

        # 2) Verify required tables exist
        if 'house_plans' not in tables:
            _print_fail('house_plans table is missing (unexpected). Check DATABASE_URL / migrations.')
            return 2
        _print_ok('house_plans table present')

        if 'blog_posts' not in tables:
            _print_fail('blog_posts table is still missing after create_all().')
            return 3
        _print_ok('blog_posts table present')

        # 3) Verify BlogPost model columns
        from app.models import BlogPost as BlogPostModel

        model_cols = set(BlogPostModel.__table__.columns.keys())
        missing_cols = sorted(REQUIRED_BLOGPOST_COLUMNS - model_cols)
        if missing_cols:
            _print_warn(f"BlogPost model is missing columns: {', '.join(missing_cols)}")
        else:
            _print_ok('BlogPost model has required columns')

        # 4) Verify FK blog_posts.plan_id -> house_plans.id
        fks = inspector.get_foreign_keys('blog_posts')
        fk_ok = False
        for fk in fks:
            if fk.get('referred_table') != 'house_plans':
                continue
            constrained = set(fk.get('constrained_columns') or [])
            referred = set(fk.get('referred_columns') or [])
            if 'plan_id' in constrained and 'id' in referred:
                fk_ok = True
                break

        if fk_ok:
            _print_ok('Foreign key verified: blog_posts.plan_id -> house_plans.id')
        else:
            _print_warn('Foreign key NOT detected (blog_posts.plan_id -> house_plans.id).')
            _print_warn('If this is Postgres, you likely need to run Alembic migrations (flask db upgrade).')

        # 5) Verify admin endpoints registered (blog module loaded)
        endpoints = set(app.view_functions.keys())
        required_endpoints = {'blog.create', 'blog.edit', 'blog.admin_list'}
        missing_endpoints = sorted(required_endpoints - endpoints)
        if missing_endpoints:
            _print_warn(f"Blog admin endpoints not registered: {', '.join(missing_endpoints)}")
            _print_warn('Ensure blog blueprint is registered in create_app() and deploy latest code.')
        else:
            _print_ok('Blog admin endpoints registered')

        _print_ok('Schema activation completed. Blog should be functional now.')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
