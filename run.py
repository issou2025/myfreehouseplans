"""
Temporary bootstrap runner for Render.

This script ensures any new columns from app.models are created via db.create_all()
prior to starting the development server. Once production schema is fully
migrated via Alembic, this file can be removed.
"""

import os

from wsgi import app
from app.extensions import db


if __name__ == '__main__':
    with app.app_context():
        # Import models to ensure metadata is fully populated before create_all().
        import app.models  # noqa: F401

        # Allow NULL so legacy rows keep working if the column is missing.
        db.create_all()

    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    app.run(host=host, port=port)