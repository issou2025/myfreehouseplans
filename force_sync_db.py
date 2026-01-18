"""One-time safe DB sync for production.

Purpose:
- Fix: psycopg2.errors.UndefinedTable: relation 'blog_posts' does not exist
- SAFE: Only creates missing tables with db.create_all()
- NEVER drops tables, NEVER deletes data

Run on Render Shell:
  python force_sync_db.py
"""

from sqlalchemy import inspect

# Import the application instance from the main entrypoint
from wsgi import app
from app.extensions import db


def main() -> int:
    with app.app_context():
        # Ensure models are imported so SQLAlchemy metadata includes BlogPost
        import app.models  # noqa: F401

        # SAFE: creates only missing tables
        db.create_all()

        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())

        if 'blog_posts' not in tables:
            print("✗ blog_posts table still missing. Run 'flask db upgrade' or verify DATABASE_URL.")
            return 2

        # Optional: verify FK exists (Postgres migrations create proper constraints)
        fk_ok = False
        try:
            fks = inspector.get_foreign_keys('blog_posts')
            for fk in fks:
                if fk.get('referred_table') != 'house_plans':
                    continue
                if 'plan_id' in (fk.get('constrained_columns') or []) and 'id' in (fk.get('referred_columns') or []):
                    fk_ok = True
                    break
        except Exception:
            pass

        print("✓ blog_posts table exists.")
        if fk_ok:
            print("✓ ForeignKey verified: blog_posts.plan_id -> house_plans.id")
        else:
            print("⚠ ForeignKey not detected via inspector (may require migrations: flask db upgrade)")

        print("✓ Done. Existing tables/data were not modified.")
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
