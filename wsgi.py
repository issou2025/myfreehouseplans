"""
WSGI Entry Point for MyFreeHousePlans Application

This module serves as the entry point for WSGI servers (like Gunicorn)
to run the Flask application in production environments.

CRITICAL PRODUCTION REQUIREMENTS:
- All environment variables must be set BEFORE this module is imported
- Database connectivity is verified during application creation
- Missing environment variables cause immediate failure with clear messages
"""

import os
import sys

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

print(f'🚀 Initializing Flask application with config: {config_name}', file=sys.stderr)

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
            missing_vars.append(f"  ❌ {var_name}: {description}")
    
    if missing_vars:
        error_msg = (
            "\n" + "="*70 + "\n"
            "❌ DEPLOYMENT FAILED: Missing required environment variables\n"
            "="*70 + "\n\n"
            + "\n".join(missing_vars)
            + "\n\n"
            "SOLUTION: Set these in your Render Dashboard:\n"
            "  1. Go to Dashboard → Your Service → Environment\n"
            "  2. Add each missing variable with appropriate values\n"
            "  3. Redeploy your application\n"
            + "="*70 + "\n"
        )
        print(error_msg, file=sys.stderr)
        raise RuntimeError('Missing required environment variables in production')
    
    print('✓ All required environment variables present', file=sys.stderr)

# Create Flask application instance
try:
    app = create_app(config_name)
    print('✓ Flask application created successfully', file=sys.stderr)
except Exception as exc:
    print(f'\n{"="*70}', file=sys.stderr)
    print('❌ FATAL: Application initialization failed', file=sys.stderr)
    print(f'{"="*70}', file=sys.stderr)
    print(f'\nError: {exc}', file=sys.stderr)
    print('\nCommon causes:', file=sys.stderr)
    print('  1. Database connection failure (check DATABASE_URL)', file=sys.stderr)
    print('  2. Missing database tables (run: flask db upgrade)', file=sys.stderr)
    print('  3. Invalid environment variable values', file=sys.stderr)
    print(f'\n{"="*70}\n', file=sys.stderr)
    raise
