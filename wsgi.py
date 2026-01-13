"""
WSGI Entry Point for MyFreeHousePlans Application

This module serves as the entry point for WSGI servers (like Gunicorn)
to run the Flask application in production environments.
"""

import os

# Load .env ONLY for local development. In production (Render), environment
# variables must be provided by the platform. Never rely on a committed file.
if os.environ.get('FLASK_ENV', '').lower() != 'production' and os.environ.get('FLASK_CONFIG', '').lower() != 'production':
	try:
		from dotenv import load_dotenv

		load_dotenv(override=False)
	except Exception:
		# python-dotenv is an optional dev convenience. Do not fail the app
		# just because dotenv isn't available.
		pass

from app import create_app

# Determine configuration name.
# - Local/dev defaults to development.
# - Production platforms (Render) must explicitly set FLASK_ENV/FLASK_CONFIG=production.
config_name = (os.getenv('FLASK_CONFIG') or os.getenv('FLASK_ENV') or 'development').lower()

# Validate required environment variables in production
if config_name == 'production':
    required_vars = {
        'SECRET_KEY': 'Required for session encryption and CSRF protection',
        'DATABASE_URL': 'Required for PostgreSQL connection',
        'ADMIN_USERNAME': 'Required for admin account creation via CLI',
        'ADMIN_EMAIL': 'Required for admin account notifications',
        'ADMIN_PASSWORD': 'Required for initial admin authentication',
    }
    
    missing_vars = []
    for var_name, description in required_vars.items():
        if not os.getenv(var_name):
            missing_vars.append(f"  - {var_name}: {description}")
    
    if missing_vars:
        error_msg = (
            "\n❌ DEPLOYMENT FAILED: Missing required environment variables\n\n"
            + "\n".join(missing_vars)
            + "\n\nSet these in your Render Dashboard under Environment Variables.\n"
        )
        raise RuntimeError(error_msg)

# Create Flask application instance exposed as module-level `app` for Gunicorn.
app = create_app(config_name)
