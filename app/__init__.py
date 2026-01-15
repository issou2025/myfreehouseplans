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
import importlib
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
# NOTE: Removed destructive bootstrap behavior. Admin seeding and any
# DROP/CREATE operations are intentionally disabled in the factory.
# Use explicit CLI commands (app.cli) to seed data in controlled environments.


def _safe_log(app, level: str, message: str, *args, **kwargs) -> None:
    """Log without risking startup due to logger misconfiguration."""
    try:
        logger = getattr(app.logger, level)
        logger(message, *args, **kwargs)
    except Exception:
        try:
            import sys

            print(f"[{level.upper()}] {message % args if args else message}", file=sys.stderr)
        except Exception:
            pass


def _force_create_tables(app) -> None:
    """Non-destructive startup schema patch.

    IMPORTANT:
        - Never drops tables.
        - Intentionally does NOT call db.create_all() to avoid creating an empty
      schema on a misconfigured/brand-new database.
    - Adds only critical missing columns via ALTER TABLE.
    """
    if os.environ.get('SKIP_STARTUP_DB_TASKS') == '1':
        _safe_log(app, 'warning', 'Skipping startup DB tasks due to SKIP_STARTUP_DB_TASKS=1')
        return

    with app.app_context():
        # 1) Verify connectivity (non-fatal)
        try:
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            _safe_log(app, 'info', '✓ Database connectivity verified')
        except Exception as exc:
            db.session.rollback()
            _safe_log(app, 'error', '✗ Database connectivity check failed (continuing): %s', exc, exc_info=True)
            return

        # 2) Import models inside context to populate metadata (avoids circular imports)
        try:
            importlib.import_module('app.models')
        except Exception as exc:
            _safe_log(app, 'error', '✗ Failed to import models during bootstrap (continuing): %s', exc, exc_info=True)
            return

        # 3) Non-fatal schema sanity check
        try:
            inspector = inspect(db.engine)
            existing = set(inspector.get_table_names())
            required = set(db.metadata.tables.keys())
            missing = sorted(required - existing)
            if missing:
                _safe_log(
                    app,
                    'warning',
                    '⚠ Schema appears incomplete. Missing tables: %s. '
                    'App will continue, but features may fail until migrations run.',
                    ', '.join(missing),
                )
            else:
                _safe_log(app, 'info', '✓ All required tables present (%d)', len(required))
        except Exception as exc:
            _safe_log(app, 'warning', '⚠ Could not verify schema completeness (continuing): %s', exc, exc_info=True)

        # 4) Patch critical columns (non-fatal)
        try:
            inspector = inspect(db.engine)
            dialect = getattr(db.engine.dialect, 'name', '')
            tables = set(inspector.get_table_names())

            def _has_column(table_name: str, column_name: str) -> bool:
                try:
                    cols = inspector.get_columns(table_name)
                except Exception:
                    return False
                return any(c.get('name') == column_name for c in cols)

            if 'users' in tables and not _has_column('users', 'role'):
                if dialect == 'postgresql':
                    db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50)"))
                else:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(50)"))
                # Preserve admin access assumption: id=1 is the owner admin.
                db.session.execute(text("UPDATE users SET role='superadmin' WHERE id=1 AND (role IS NULL OR role='')"))
                db.session.execute(text("UPDATE users SET role='customer' WHERE role IS NULL OR role=''"))

            if 'house_plans' in tables and not _has_column('house_plans', 'created_by_id'):
                if dialect == 'postgresql':
                    db.session.execute(text("ALTER TABLE house_plans ADD COLUMN IF NOT EXISTS created_by_id INTEGER"))
                else:
                    db.session.execute(text("ALTER TABLE house_plans ADD COLUMN created_by_id INTEGER"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_house_plans_created_by_id ON house_plans (created_by_id)"))

            if 'house_plans' in tables and _has_column('house_plans', 'created_by_id') and 'users' in tables:
                admin_id = db.session.execute(text("SELECT id FROM users WHERE id=1")).scalar()
                if not admin_id:
                    admin_id = db.session.execute(text("SELECT id FROM users WHERE role='superadmin' ORDER BY id ASC LIMIT 1")).scalar()
                if admin_id:
                    db.session.execute(
                        text("UPDATE house_plans SET created_by_id = :admin_id WHERE created_by_id IS NULL"),
                        {'admin_id': int(admin_id)},
                    )

            db.session.commit()
            _safe_log(app, 'info', '✓ Startup schema patch complete (role/created_by_id)')
        except Exception as exc:
            db.session.rollback()
            _safe_log(app, 'error', '✗ Startup schema patch failed (continuing): %s', exc, exc_info=True)
            # Continue; admin dashboard will surface the underlying SQL error.

        # 5) Fail-safe admin seeding (non-fatal)
        # This exists specifically to recover access on fresh deployments.
        # It uses lazy imports INSIDE app_context to avoid circular imports.
        if os.environ.get('SKIP_ADMIN_SEED') == '1':
            _safe_log(app, 'warning', 'Skipping admin seeding due to SKIP_ADMIN_SEED=1')
            return

        try:
            # If the users table doesn't exist, seeding cannot happen.
            inspector = inspect(db.engine)
            if 'users' not in set(inspector.get_table_names()):
                _safe_log(app, 'warning', 'Skipping admin seed: users table is missing')
                return

            # Requirements (with safe env overrides):
            # - Check for email='ton-email@exemple.com'
            # - Create username='admin'
            # - Password hashed via generate_password_hash('ton_mot_de_passe_secret')
            # - Admin flag: role == 'superadmin'
            admin_email = os.environ.get('ADMIN_EMAIL') or 'ton-email@exemple.com'
            admin_username = os.environ.get('ADMIN_USERNAME') or 'admin'
            admin_password = os.environ.get('ADMIN_PASSWORD') or 'ton_mot_de_passe_secret'

            if not admin_email:
                _safe_log(app, 'warning', 'Skipping admin seed: ADMIN_EMAIL not set and no default provided')
                return

            # Loud warning if defaults are used in production.
            if app.config.get('ENV') == 'production':
                if admin_email == 'ton-email@exemple.com' or admin_password == 'ton_mot_de_passe_secret':
                    _safe_log(
                        app,
                        'warning',
                        '⚠ Insecure default admin credentials are in use. '
                        'Set ADMIN_EMAIL/ADMIN_PASSWORD in Render dashboard immediately.'
                    )

            # Lazy imports inside context to avoid circular import crashes.
            from werkzeug.security import generate_password_hash
            from app.models import User

            existing_admin = User.query.filter_by(email=admin_email).first()
            if existing_admin:
                _safe_log(app, 'info', '✓ Admin seed: user already exists for email=%s', admin_email)
                return

            new_admin = User(
                username=admin_username,
                email=admin_email,
                password_hash=generate_password_hash(admin_password),
                role='superadmin',
                is_active=True,
            )
            db.session.add(new_admin)
            db.session.commit()
            _safe_log(app, 'warning', '✓ Admin seed: created superadmin user for email=%s', admin_email)
        except IntegrityError:
            # Another worker (or another deploy) created it concurrently.
            db.session.rollback()
            _safe_log(app, 'info', '✓ Admin seed: user already created by another process')
        except Exception as exc:
            db.session.rollback()
            _safe_log(app, 'error', '✗ Admin seed failed (continuing): %s', exc, exc_info=True)


def create_app(config_name='default'):
    """
    Application factory function
    
    Args:
        config_name (str): Configuration name ('development', 'production', 'testing')
    
    Returns:
        Flask: Configured Flask application instance
    """
    
    # Normalize config name
    config_name = (config_name or 'default').lower()

    # Create Flask app instance
    app = Flask(__name__)
    
    # Load configuration
    # IMPORTANT: Instantiate the config object so @property values (like
    # ProductionConfig.SQLALCHEMY_DATABASE_URI) are evaluated correctly.
    cfg = config.get(config_name) or config['default']
    cfg_obj = cfg() if isinstance(cfg, type) else cfg
    app.config.from_object(cfg_obj)

    # Ensure SECRET_KEY exists for any environment that uses sessions/CSRF.
    # - Production: enforced via environment variable (fail fast).
    # - Development/default: generate an ephemeral key if missing to avoid 500s
    #   on pages that render CSRF-protected forms.
    if config_name == 'production':
        secret = app.config.get('SECRET_KEY')
        if not secret:
            app.logger.error('Production requires SECRET_KEY to be set via environment variable')
            raise RuntimeError('Missing SECRET_KEY in production')
    else:
        if not app.config.get('SECRET_KEY'):
            app.config['SECRET_KEY'] = os.urandom(32)
            app.logger.warning('SECRET_KEY was missing; generated an ephemeral key for this process.')

    # Enforce secure production configuration as early as possible (before
    # extensions initialize and potentially import DB drivers).
    if config_name == 'production':
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        if not db_uri:
            app.logger.error('Production requires DATABASE_URL (SQLALCHEMY_DATABASE_URI) to be set')
            raise RuntimeError('Missing DATABASE_URL in production')

        # Extra defensive fix: Render/Heroku often provide postgres:// which
        # SQLAlchemy rejects. This is also handled in ProductionConfig, but we
        # normalize here too to be robust.
        if isinstance(db_uri, str) and db_uri.startswith('postgres://'):
            app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://' + db_uri[len('postgres://'):]
            app.logger.warning('✓ Normalized DATABASE_URL prefix: postgres:// -> postgresql://')
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']

        if db_uri.strip().startswith('sqlite:'):
            app.logger.error('Production requires PostgreSQL (DATABASE_URL must not be sqlite): %s', db_uri)
            raise RuntimeError('SQLite not allowed in production')
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # Ensure protected uploads folder exists
    os.makedirs(app.config.get('PROTECTED_UPLOAD_FOLDER', app.config['UPLOAD_FOLDER']), exist_ok=True)

    # GeoIP (read-only) initialization
    project_root = os.path.abspath(os.path.join(app.root_path, os.pardir))
    app.config.setdefault('GEOIP_DB_PATH', os.path.join(project_root, 'GeoLite2-Country.mmdb'))
    try:
        from app.utils.geoip import init_geoip_reader
        init_geoip_reader(app.config.get('GEOIP_DB_PATH'), app.logger)
    except Exception:
        # GeoIP is optional and must never break startup.
        pass
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)

    # Zero-touch bootstrap (Render-friendly): force-create tables and NEVER
    # hard-fail startup if schema is incomplete.
    # This is intentionally resilient, and imports models inside app_context
    # to avoid circular import issues.
    _force_create_tables(app)

    
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

    @app.after_request
    def _apply_security_headers(response):
        """Apply safe security headers without affecting app logic."""
        csp = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self' https://wa.me https://gumroad.com https://gum.co; "
            "frame-ancestors 'none'; "
            "img-src 'self' data: https:; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "connect-src 'self';"
        )
        response.headers.setdefault('Content-Security-Policy', csp)
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-site')
        return response

    @app.teardown_appcontext
    def _cleanup_appcontext(exc):
        """Ensure scoped sessions are removed when the app context ends."""
        try:
            db.session.remove()
        except Exception as remove_exc:
            try:
                app.logger.error('Session remove during appcontext teardown failed: %s', remove_exc, exc_info=True)
            except Exception:
                import traceback
                print(traceback.format_exc())
        return None

    @app.route('/favicon.ico')
    def favicon_placeholder():  # pragma: no cover - trivial route
        return ('', 204)
    
    return app


def register_blueprints(app):
    """Register Flask blueprints"""
    
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.health import health_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(health_bp)  # No prefix - accessible at /health


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
        from app.utils.geoip import get_country_for_ip

        def query_args(exclude=None):
            exclude = set(exclude or [])
            args = request.args.to_dict(flat=True)
            for key in exclude:
                args.pop(key, None)
            return args

        def client_ip():
            forwarded = request.headers.get('X-Forwarded-For', '')
            if forwarded:
                return forwarded.split(',')[0].strip()
            return request.remote_addr or '0.0.0.0'

        visitor_ip = client_ip()
        visitor_country = get_country_for_ip(visitor_ip)
        return {
            'site_name': app.config['SITE_NAME'],
            'site_description': app.config['SITE_DESCRIPTION'],
            'site_url': app.config['SITE_URL'],
            'upload_url': upload_url,
            'picture_tag': picture_tag,
            'CARD_PRESET': CARD_PRESET,
            'HERO_PRESET': HERO_PRESET,
            'query_args': query_args,
            'client_ip': visitor_ip,
            'visitor_country': visitor_country,
            'geoip_country': get_country_for_ip,
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
    from app.cli_diagnostics import diagnose_db_command
    
    app.cli.add_command(create_admin_command)
    app.cli.add_command(reset_admin_password_command)
    app.cli.add_command(seed_categories_command)
    app.cli.add_command(seed_sample_plans_command)
    app.cli.add_command(diagnose_db_command)


def register_request_hooks(app):
    """Attach request hooks for analytics tracking."""

    from flask import request, g
    from flask_login import current_user

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
        if path == '/favicon.ico':
            g.visit_track = None
            return
        if path.startswith('/static/') or request.endpoint == 'static':
            g.visit_track = None
            return
        if path.startswith('/admin'):
            g.visit_track = None
            return
        if request.method not in ('GET', 'POST'):
            g.visit_track = None
            return
        if current_user.is_authenticated and getattr(current_user, 'role', None) == 'superadmin':
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
            # Analytics failures should not break the request, but we must log them
            # Use print() as fallback if logger itself is broken
            try:
                app.logger.warning('Visitor logging failed: %s', exc, exc_info=True)
            except Exception as log_exc:
                # Last resort: write to stderr if logger is completely broken
                import sys
                print(f"CRITICAL: Logger failure in visitor tracking: {log_exc}", file=sys.stderr)
                print(f"Original error: {exc}", file=sys.stderr)
        finally:
            g.visit_track = None
        return response

    @app.teardown_request
    def _cleanup_sessions(exc):
        """Guarantee DB sessions are rolled back and removed every request."""

        if exc is not None:
            try:
                db.session.rollback()
            except Exception as rollback_exc:
                try:
                    app.logger.error('Rollback during teardown failed: %s', rollback_exc, exc_info=True)
                except Exception:
                    import traceback
                    print(traceback.format_exc())
        else:
            # Even when the request was successful we still clear any pending state.
            try:
                db.session.rollback()
            except Exception:
                pass

        try:
            db.session.remove()
        except Exception as remove_exc:
            try:
                app.logger.error('Session remove during teardown failed: %s', remove_exc, exc_info=True)
            except Exception:
                import traceback
                print(traceback.format_exc())
        return None
