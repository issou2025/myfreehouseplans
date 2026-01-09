"""
WSGI Entry Point for MyFreeHousePlan Application

This module serves as the entry point for WSGI servers (like Gunicorn)
to run the Flask application in production environments.
"""

from app import create_app
from dotenv import load_dotenv
import os

# Load environment variables from .env file if it exists
load_dotenv()

# Determine configuration name; default to production for Render
config_name = os.getenv('FLASK_CONFIG') or os.getenv('FLASK_ENV', 'production')

# Create Flask application instance exposed as module-level ``app`` for Gunicorn
app = create_app(config_name)
