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

# Create Flask application instance exposed as module-level `app` for Gunicorn.
app = create_app(config_name)
