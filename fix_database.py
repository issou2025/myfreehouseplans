"""Safe DB repair: create missing tables without dropping existing ones."""
import os

from app import create_app
from app.extensions import db


def main() -> None:
    # Ensure production config is used when DATABASE_URL is set (Render)
    config_name = os.getenv("FLASK_CONFIG") or os.getenv("FLASK_ENV") or "production"
    app = create_app(config_name.lower())

    with app.app_context():
        # Import models so metadata is populated
        import app.models  # noqa: F401

        # SAFE: creates ONLY missing tables, never drops
        db.create_all()
        print("✓ db.create_all() completed. Missing tables created if any.")


if __name__ == "__main__":
    main()
