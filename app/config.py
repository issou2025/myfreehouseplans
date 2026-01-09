"""
Configuration Module for MyFreeHousePlan Application

This module defines configuration classes for different environments:
- DevelopmentConfig: Local development with SQLite
- ProductionConfig: Production deployment with PostgreSQL
- TestingConfig: Automated testing configuration
"""

import os
from datetime import timedelta


class Config:
    """Base configuration with common settings"""
    
    # Secret key for session management and CSRF protection
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    
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
    # Protected uploads (not served by static). Used for paid downloads and private artifacts.
    PROTECTED_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads_protected')
    PROTECTED_FOLDERS = {'pdfs', 'support'}
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Remember me cookie duration
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # Security headers
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # SEO Configuration
    SITE_NAME = 'MyFreeHousePlans'
    SITE_DESCRIPTION = 'Premium house plans, thoughtfully detailed and ready to build.'
    SITE_URL = os.environ.get('SITE_URL', 'https://www.myfreehouseplans.com')
    SITE_KEYWORDS = 'house plans, architectural plans, home designs, blueprints'
    
    # Admin configuration
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'entreprise2rc@gmail.com')


class DevelopmentConfig(Config):
    """Development environment configuration"""
    
    DEBUG = True
    TESTING = False
    
    # SQLite for development
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'myfreehouseplan.db')
    
    # Disable secure cookies for local development
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    
    # Enable SQL query logging
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Production environment configuration"""
    
    DEBUG = False
    TESTING = False
    
    # PostgreSQL for production
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    # If using Render/Heroku, they provide DATABASE_URL with postgres://
    # but SQLAlchemy 1.4+ requires postgresql://
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
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
