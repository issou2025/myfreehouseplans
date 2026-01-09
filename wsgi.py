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

# Create Flask application instance
app = create_app(os.getenv('FLASK_ENV', 'production'))

if __name__ == '__main__':
    # This is for development only
    # In production, use: gunicorn wsgi:app
    app.run(debug=False)
