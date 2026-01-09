"""
Flask Application Factory

This module implements the application factory pattern for creating
Flask application instances with different configurations.
"""

from flask import Flask, render_template
from app.config import config
from app.extensions import db, migrate, login_manager, mail
import os


def create_app(config_name='default'):
    """
    Application factory function
    
    Args:
        config_name (str): Configuration name ('development', 'production', 'testing')
    
    Returns:
        Flask: Configured Flask application instance
    """
    
    # Create Flask app instance
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # Ensure protected uploads folder exists
    os.makedirs(app.config.get('PROTECTED_UPLOAD_FOLDER', app.config['UPLOAD_FOLDER']), exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register template context processors
    register_template_processors(app)
    
    # Register shell context
    register_shell_context(app)

    # Register CLI commands
    register_cli_commands(app)
    
    return app


def register_blueprints(app):
    """Register Flask blueprints"""
    
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')


def register_error_handlers(app):
    """Register error handlers for common HTTP errors"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors"""
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors"""
        app.logger.exception('Unhandled exception (500): %s', error)
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """Handle 403 errors"""
        return render_template('errors/403.html'), 403


def register_template_processors(app):
    """Register context processors for templates"""
    
    @app.context_processor
    def inject_site_config():
        """Inject site configuration into all templates"""
        return {
            'site_name': app.config['SITE_NAME'],
            'site_description': app.config['SITE_DESCRIPTION'],
            'site_url': app.config['SITE_URL'],
        }


def register_shell_context(app):
    """Register shell context for Flask CLI"""
    
    @app.shell_context_processor
    def make_shell_context():
        """Make database models available in Flask shell"""
        from app.models import User, HousePlan, Category, Order, ContactMessage
        return {
            'db': db,
            'User': User,
            'HousePlan': HousePlan,
            'Category': Category,
            'Order': Order,
            'ContactMessage': ContactMessage,
        }


def register_cli_commands(app):
    """Register custom Flask CLI commands."""
    from app.cli import create_admin_command, seed_categories_command, seed_sample_plans_command
    app.cli.add_command(create_admin_command)
    app.cli.add_command(seed_categories_command)
    app.cli.add_command(seed_sample_plans_command)
