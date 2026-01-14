"""
Configuration Module for MyFreeHousePlans Application

This module defines configuration classes for different environments:
- DevelopmentConfig: Local development with SQLite
- ProductionConfig: Production deployment with PostgreSQL
- TestingConfig: Automated testing configuration
"""

import os
from pathlib import Path
from datetime import timedelta


class Config:
    """Base configuration with common settings"""
    
    # Secret key for session management and CSRF protection.
    # DO NOT provide an insecure default here.
    # - In development, we load from .env (see wsgi.py) or you can set it explicitly.
    # - In production, the app factory enforces presence.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # Database configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True

    # Make database connections more resilient in production (stale connections,
    # temporary network blips). Safe defaults for all environments.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    
    # Pagination
    PLANS_PER_PAGE = 12
    ORDERS_PER_PAGE = 20
    
    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@myfreehouseplans.com')
    
    # File upload configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'dwg', 'doc', 'docx'}
    # Placeholder used when an expected local image is missing.
    # (Kept in static so it always resolves in templates.)
    IMAGE_PLACEHOLDER = 'images/placeholder.svg'
    # Protected uploads (not served by static). Used for paid downloads and private artifacts.
    PROTECTED_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads_protected')
    PROTECTED_FOLDERS = {'pdfs', 'support'}
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=720)
    SESSION_REFRESH_EACH_REQUEST = True
    
    # Remember me cookie duration
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # Security headers
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # SEO Configuration
    SITE_NAME = 'MyFreeHousePlans'
    SITE_DESCRIPTION = 'Premium house plans, thoughtfully detailed and ready to build.'
    SITE_URL = os.environ.get('SITE_URL', 'https://www.myfreehouseplans.com')
    SITE_KEYWORDS = 'house plans, architectural plans, home designs, blueprints'
    
    # Admin configuration
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@myfreehouseplans.com')

    # Cloudinary (Render): provide CLOUDINARY_URL in environment.
    CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')


class DevelopmentConfig(Config):
    """Development environment configuration"""
    
    DEBUG = True
    TESTING = False
    
    # SQLite for development
    # IMPORTANT (Windows): SQLAlchemy sqlite URLs must use forward slashes.
    # Using os.path.join will introduce backslashes which can break DB opening.
    _project_root = Path(__file__).resolve().parent.parent
    _default_db_path = (_project_root / 'myfreehouseplan.db').resolve()

    _env_db_url = os.environ.get('DATABASE_URL')
    if _env_db_url and _env_db_url.strip().startswith('sqlite:'):
        _env_db_url = _env_db_url.replace('\\', '/')

    SQLALCHEMY_DATABASE_URI = _env_db_url or f"sqlite:///{_default_db_path.as_posix()}"
    
    # Disable secure cookies for local development
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    
    # Enable SQL query logging
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Production environment configuration"""
    
    DEBUG = False
    TESTING = False
    
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        """
        Dynamically construct production database URI with proper fixes.
        
        This MUST be a property to ensure it's evaluated at request time,
        not at class definition time.
        
        ARCHITECTURAL RATIONALE:
        - Render/Heroku provide DATABASE_URL with postgres:// prefix
        - SQLAlchemy 1.4+ requires postgresql:// prefix
        - SSL is required for managed PostgreSQL (security)
        - Property evaluation ensures environment changes are reflected
        """
        db_uri = os.environ.get('DATABASE_URL')
        
        if not db_uri:
            # Log detailed error for debugging
            import sys
            print('❌ FATAL: DATABASE_URL not set in environment', file=sys.stderr)
            print('Available env vars:', list(os.environ.keys()), file=sys.stderr)
            return None
        
        original_uri = db_uri
        
        # Fix postgres:// -> postgresql:// (Render/Heroku compatibility)
        if db_uri.startswith('postgres://'):
            db_uri = 'postgresql://' + db_uri[len('postgres://'):]
            print(f'✓ Fixed DATABASE_URL prefix: postgres:// -> postgresql://', file=sys.stderr)
        
        # Enforce SSL for PostgreSQL connections (security best practice)
        if db_uri.startswith('postgresql://'):
            if 'sslmode=' not in db_uri:
                separator = '&' if '?' in db_uri else '?'
                db_uri = f"{db_uri}{separator}sslmode=require"
                print(f'✓ Added SSL requirement to PostgreSQL connection', file=sys.stderr)
        
        # Log sanitized connection info (hide password)
        try:
            from urllib.parse import urlparse
            parsed = urlparse(db_uri)
            safe_uri = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port or 5432}{parsed.path}"
            print(f'✓ Database URI configured: {safe_uri}', file=sys.stderr)
        except Exception:
            pass
        
        return db_uri
    
    # Disable SQL query logging in production
    SQLALCHEMY_ECHO = False
    
    # Production security
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing environment configuration"""
    
    TESTING = True
    DEBUG = True
    
    # In-memory SQLite for fast testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Disable secure cookies for testing
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False


# Configuration dictionary for easy access
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
