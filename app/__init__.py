"""
Flask Application Factory

This module implements the application factory pattern for creating
Flask application instances with different configurations.
"""

from flask import Flask, render_template
from app.config import config
from app.extensions import db, migrate, login_manager, mail
from datetime import datetime
import os
from sqlalchemy import inspect


# NOTE: Removed destructive bootstrap behavior. Admin seeding and any
# DROP/CREATE operations are intentionally disabled in the factory.
# Use explicit CLI commands (app.cli) to seed data in controlled environments.


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
    
    # Database initialization and verification. Do NOT perform destructive
    # operations in production. Enforce presence of a persistent DB and
    # abort startup if the production DB appears missing or ephemeral.
    with app.app_context():
        try:
            # Import all models to ensure they're registered with SQLAlchemy
            from app.models import User, HousePlan, Category, Order, ContactMessage, Visitor

            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names() or []

            if config_name == 'production':
                uri = app.config.get('SQLALCHEMY_DATABASE_URI')
                if not uri:
                    app.logger.error('Production requires SQLALCHEMY_DATABASE_URI to be set to a persistent database.')
                    raise RuntimeError('Missing SQLALCHEMY_DATABASE_URI in production')
                if uri.strip().startswith('sqlite:///:memory:'):
                    app.logger.error('In-memory SQLite is forbidden in production.')
                    raise RuntimeError('In-memory DB not allowed in production')

                # Prefer absolute /data mount for sqlite in production containers
                if uri.startswith('sqlite:'):
                    # Accept both sqlite:////data/... and sqlite:///data/...
                    if '/data/' not in uri and not uri.startswith('sqlite:///'):
                        app.logger.warning('Production sqlite database path does not contain /data/: %s', uri)

                    # Allow migrations to run: if we're executing Flask-Migrate commands
                    # (e.g., `flask db upgrade`) permit empty DB so alembic can create schema.
                    import sys
                    cli_args = ' '.join(sys.argv).lower()
                    running_migration = ('db' in sys.argv) or ('upgrade' in sys.argv) or ('alembic' in cli_args)
                    if not existing_tables and not running_migration:
                        # Opt-in automatic initialization when explicitly allowed via env var
                        allow_init = os.environ.get('ALLOW_INIT_ON_STARTUP', '').lower() in ('1', 'true', 'yes')
                        if allow_init:
                            try:
                                from alembic.config import Config as AlembicConfig
                                from alembic import command as alembic_command

                                # Try locating alembic.ini in project
                                migrations_ini = os.path.abspath(os.path.join(os.getcwd(), 'migrations', 'alembic.ini'))
                                if not os.path.exists(migrations_ini):
                                    # fallback: package-relative
                                    migrations_ini = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'migrations', 'alembic.ini'))

                                if os.path.exists(migrations_ini):
                                    alembic_cfg = AlembicConfig(migrations_ini)
                                    alembic_cfg.set_main_option('sqlalchemy.url', app.config['SQLALCHEMY_DATABASE_URI'])
                                    app.logger.info('Applying alembic migrations from %s', migrations_ini)
                                    alembic_command.upgrade(alembic_cfg, 'head')
                                    app.logger.info('Migrations applied successfully during startup')
                                    inspector = inspect(db.engine)
                                    existing_tables = inspector.get_table_names() or []
                                else:
                                    app.logger.error('alembic.ini not found; cannot run migrations automatically: %s', migrations_ini)
                                    raise RuntimeError('Missing alembic.ini for automatic migrations')
                            except Exception as ex:
                                app.logger.exception('Automatic migration attempt failed: %s', ex)
                                raise
                        else:
                            # In production we must NOT perform automatic schema creation.
                            # Allow the application to start so that operators can run
                            # migrations (`flask db upgrade`) from CI/CD or the deploy
                            # platform (Render). Log a warning so the situation is visible
                            # in logs but do not abort process startup.
                            app.logger.warning(
                                'Production database appears empty; continuing startup. '
                                'Do NOT use db.create_all() in production. Apply migrations with Alembic/Flask-Migrate.'
                            )

                app.logger.info('Production database verified with %d existing tables', len(existing_tables))
            # Ensure messaging table exists so inbound messages are never lost.
            # Create only the `messages` table if it's missing; do not perform
            # broad schema changes here. Failures are logged but do not abort
            # startup to preserve availability.
            try:
                if 'messages' not in (inspect(db.engine).get_table_names() or []):
                    from app.models import ContactMessage
                    ContactMessage.__table__.create(bind=db.engine, checkfirst=True)
                    app.logger.info('Created messages table during startup')
            except Exception as ex:
                # Log but do not raise: admin can run full migrations via CI/Render.
                app.logger.exception('Failed to ensure messages table exists at startup: %s', ex)
            else:
                # Non-production: create tables if missing, but do NOT drop existing data
                if not existing_tables:
                    db.create_all()
                    app.logger.info('Created database tables for non-production environment')
        except Exception as e:
            app.logger.error('Database initialization/verification failed: %s', e)
            # Fail fast in production to avoid accidental data loss
            raise
    
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

    # Register request lifecycle hooks
    register_request_hooks(app)
    
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
        from app.utils.media import upload_url
        from app.utils.responsive_media import picture_tag, CARD_PRESET, HERO_PRESET
        from flask import request

        def query_args(exclude=None):
            exclude = set(exclude or [])
            args = request.args.to_dict(flat=True)
            for key in exclude:
                args.pop(key, None)
            return args
        return {
            'site_name': app.config['SITE_NAME'],
            'site_description': app.config['SITE_DESCRIPTION'],
            'site_url': app.config['SITE_URL'],
            'upload_url': upload_url,
            'picture_tag': picture_tag,
            'CARD_PRESET': CARD_PRESET,
            'HERO_PRESET': HERO_PRESET,
            'query_args': query_args,
        }


def register_shell_context(app):
    """Register shell context for Flask CLI"""
    
    @app.shell_context_processor
    def make_shell_context():
        """Make database models available in Flask shell"""
        from app.models import User, HousePlan, Category, Order, ContactMessage, Visitor
        return {
            'db': db,
            'User': User,
            'HousePlan': HousePlan,
            'Category': Category,
            'Order': Order,
            'ContactMessage': ContactMessage,
            'Visitor': Visitor,
        }


def register_cli_commands(app):
    """Register custom Flask CLI commands."""
    from app.cli import (
        create_admin_command,
        reset_admin_password_command,
        seed_categories_command,
        seed_sample_plans_command
    )
    app.cli.add_command(create_admin_command)
    app.cli.add_command(reset_admin_password_command)
    app.cli.add_command(seed_categories_command)
    app.cli.add_command(seed_sample_plans_command)


def register_request_hooks(app):
    """Attach request hooks for analytics tracking."""

    from flask import request, g

    def _client_ip():
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.remote_addr or '0.0.0.0'

    @app.before_request
    def _prepare_visit_tracking():
        path = (request.path or '/').strip()
        if not path:
            path = '/'
        if path.startswith('/static/') or request.endpoint == 'static':
            g.visit_track = None
            return
        if request.method not in ('GET', 'POST'):
            g.visit_track = None
            return
        g.visit_track = {
            'timestamp': datetime.utcnow(),
            'ip': _client_ip(),
            'ua': (request.headers.get('User-Agent') or '')[:500],
            'page': path[:255],
        }

    @app.after_request
    def _persist_visit(response):
        payload = getattr(g, 'visit_track', None)
        if not payload:
            return response
        try:
            from app.models import Visitor
            visit = Visitor(
                visit_date=payload['timestamp'].date(),
                visitor_name=payload.get('name'),
                email=payload.get('email'),
                ip_address=payload['ip'],
                user_agent=payload['ua'],
                page_visited=payload['page'],
                created_at=payload['timestamp'],
            )
            db.session.add(visit)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            try:
                app.logger.warning('Visitor logging failed: %s', exc)
            except Exception:
                pass
        finally:
            g.visit_track = None
        return response
