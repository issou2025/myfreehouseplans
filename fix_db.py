"""Safe DB repair: create missing tables without dropping existing ones."""
import os

from sqlalchemy import inspect

from app import create_app
from app.extensions import db


def main() -> None:
    config_name = os.getenv("FLASK_CONFIG") or os.getenv("FLASK_ENV") or "production"
    app = create_app(config_name.lower())

    with app.app_context():
        # Import models so metadata is populated
        import app.models  # noqa: F401

        # SAFE: creates ONLY missing tables, never drops
        db.create_all()

        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        if 'blog_posts' in tables:
            print("✓ blog_posts table is present. Database is synced.")
        else:
            print("⚠ blog_posts table is still missing. Check database connection and migrations.")


if __name__ == "__main__":
    main()
