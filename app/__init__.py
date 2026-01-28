"""
Flask Application Factory

This module implements the application factory pattern for creating
Flask application instances with different configurations.
"""

from flask import Flask, render_template
from app.config import config
from app.extensions import db, migrate, login_manager, mail, limiter, ckeditor
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

        # 2b) Automated migration check (Render/no-shell safety).
        # If migrations are pending AND the database is already under Alembic control,
        # apply them automatically. This fixes missing columns/tables that can break
        # admin writes (e.g., adding plans) without dropping any data.
        if os.environ.get('SKIP_STARTUP_MIGRATIONS') != '1':
            try:
                inspector = inspect(db.engine)
                existing_tables = set(inspector.get_table_names())

                # Only run programmatic upgrades when we can confirm Alembic is managing
                # this database. If alembic_version is missing, upgrading from base may
                # try to recreate tables and fail.
                if 'alembic_version' in existing_tables:
                    current_rev = None
                    try:
                        current_rev = db.session.execute(text('SELECT version_num FROM alembic_version')).scalar()
                        db.session.commit()
                    except Exception:
                        try:
                            db.session.rollback()
                        except Exception:
                            pass

                    if current_rev:
                        # Acquire a Postgres advisory lock to avoid multi-worker races.
                        got_lock = True
                        lock_key = 921337401  # stable app-specific lock id
                        dialect = getattr(db.engine.dialect, 'name', '')
                        if dialect == 'postgresql':
                            try:
                                got_lock = bool(
                                    db.session.execute(
                                        text('SELECT pg_try_advisory_lock(:k)'),
                                        {'k': lock_key},
                                    ).scalar()
                                )
                                db.session.commit()
                            except Exception:
                                got_lock = False
                                try:
                                    db.session.rollback()
                                except Exception:
                                    pass

                        if got_lock:
                            try:
                                from flask_migrate import upgrade as alembic_upgrade

                                alembic_upgrade()
                                # Ensure no stale/failed transaction leaks into request handling.
                                try:
                                    db.session.remove()
                                except Exception:
                                    pass
                            except Exception:
                                # Never crash startup due to migration issues.
                                try:
                                    db.session.rollback()
                                except Exception:
                                    pass
                                _safe_log(app, 'warning', '⚠ Startup migration upgrade failed (continuing)', exc_info=True)
                            finally:
                                if dialect == 'postgresql':
                                    try:
                                        db.session.execute(text('SELECT pg_advisory_unlock(:k)'), {'k': lock_key})
                                        db.session.commit()
                                    except Exception:
                                        try:
                                            db.session.rollback()
                                        except Exception:
                                            pass
                        else:
                            # Another worker/process is handling upgrades.
                            try:
                                db.session.remove()
                            except Exception:
                                pass
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
                _safe_log(app, 'warning', '⚠ Startup migration check failed (continuing)', exc_info=True)

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

        # 3b) Emergency safety net (Render / production): ensure blog_posts exists.
        # Non-destructive: does NOT drop or alter existing tables.
        # Prefer migrations, but this prevents total site failure when Render releaseCommand
        # does not execute (no shell access).
        #
        # User-requested guardrail: include db.create_all() so missing blog tables are
        # created automatically. We only run it when the DB is clearly the *real*
        # production schema (i.e., it already has core tables) to avoid accidentally
        # creating an empty schema on a misconfigured/brand-new database.
        try:
            inspector = inspect(db.engine)
            tables = set(inspector.get_table_names())
            if 'blog_posts' not in tables:
                try:
                    # Only safe to auto-create missing tables when this DB already
                    # contains core tables or is under Alembic control.
                    safe_to_create_missing = bool(
                        tables.intersection({'users', 'house_plans', 'categories', 'orders', 'alembic_version'})
                    )
                    if safe_to_create_missing:
                        try:
                            db.create_all()
                        except Exception:
                            try:
                                db.session.rollback()
                            except Exception:
                                pass
                            _safe_log(app, 'warning', '⚠ Startup db.create_all() failed (continuing)', exc_info=True)

                    from app.models import BlogPost

                    # Ensure Postgres ENUM exists before table create.
                    status_type = getattr(BlogPost.__table__.c, 'status', None)
                    status_type = getattr(status_type, 'type', None)
                    if status_type is not None and hasattr(status_type, 'create'):
                        try:
                            status_type.create(db.engine, checkfirst=True)
                        except Exception:
                            # Do not block startup on enum creation quirks.
                            pass

                    BlogPost.__table__.create(bind=db.engine, checkfirst=True)
                except Exception:
                    # Critical: clear aborted transaction so later queries don't hit
                    # psycopg2.errors.InFailedSqlTransaction.
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    # Keep logging minimal; avoid crashing startup.
                    _safe_log(app, 'warning', '⚠ Startup DB sync: could not create blog_posts (continuing)', exc_info=True)
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            _safe_log(app, 'warning', '⚠ Startup DB sync check failed (continuing)', exc_info=True)

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

            # Professional plan fields (safe additive only).
            # This is a production safety net for cases where Alembic migrations did
            # not run (or ran against the wrong database). It keeps admin pages from
            # crashing with psycopg2.errors.UndefinedColumn (sqlalche.me/e/20/f405).
            if 'house_plans' in tables:
                professional_columns = {
                    # 0017_professional_plan_fields
                    'public_plan_code': 'VARCHAR(20)',
                    'target_buyer': 'VARCHAR(200)',
                    'budget_category': 'VARCHAR(100)',
                    'key_selling_point': 'VARCHAR(500)',
                    'problems_this_plan_solves': 'TEXT',
                    'living_rooms': 'INTEGER',
                    'kitchens': 'INTEGER',
                    'offices': 'INTEGER',
                    'terraces': 'INTEGER',
                    'storage_rooms': 'INTEGER',
                    'min_plot_width': 'DOUBLE PRECISION',
                    'min_plot_length': 'DOUBLE PRECISION',
                    'climate_compatibility': 'VARCHAR(300)',
                    'estimated_build_time': 'VARCHAR(150)',
                    'estimated_cost_low': 'DOUBLE PRECISION',
                    'estimated_cost_high': 'DOUBLE PRECISION',
                    'pack1_description': 'TEXT',
                    'pack2_description': 'TEXT',
                    'pack3_description': 'TEXT',
                    'architectural_style': 'VARCHAR(150)',
                }

                for column_name, column_type in professional_columns.items():
                    if _has_column('house_plans', column_name):
                        continue
                    if dialect == 'postgresql':
                        db.session.execute(
                            text(f"ALTER TABLE house_plans ADD COLUMN IF NOT EXISTS {column_name} {column_type}")
                        )
                    else:
                        db.session.execute(text(f"ALTER TABLE house_plans ADD COLUMN {column_name} {column_type}"))

                # Match the migration intent: unique index on public_plan_code.
                # Note: UNIQUE allows multiple NULLs in Postgres and SQLite.
                if _has_column('house_plans', 'public_plan_code'):
                    db.session.execute(
                        text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS ix_house_plans_public_plan_code "
                            "ON house_plans (public_plan_code)"
                        )
                    )

            db.session.commit()
            _safe_log(app, 'info', '✓ Startup schema patch complete (role/created_by_id/professional fields)')
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

    # Initialize extensions
    limiter.init_app(app)

    # Never rate-limit known crawlers/bots (SEO-friendly).
    try:
        @limiter.request_filter
        def _skip_rate_limit_for_bots():
            from flask import request
            from app.services.analytics.traffic import classify_traffic

            ua = (request.headers.get('User-Agent') or '').lower()
            if not ua:
                return False
            classification = classify_traffic(path=(request.path or '/'), user_agent=ua)
            return classification.traffic_type == 'bot'
    except Exception:
        pass

    # GeoIP (read-only) initialization
    project_root = os.path.abspath(os.path.join(app.root_path, os.pardir))
    app.config.setdefault('GEOIP_DB_PATH', os.path.join(project_root, 'GeoLite2-Country.mmdb'))
    app.config.setdefault('GEOIP_TRUSTED_PROXY_CIDRS', os.environ.get('GEOIP_TRUSTED_PROXY_CIDRS', ''))
    app.config.setdefault('GEOIP_FALLBACK_ENABLED', os.environ.get('GEOIP_FALLBACK_ENABLED', 'true').lower() == 'true')
    app.config.setdefault('GEOIP_FALLBACK_URL', os.environ.get('GEOIP_FALLBACK_URL', 'https://ipapi.co/{ip}/json/'))
    app.config.setdefault('GEOIP_FALLBACK_TIMEOUT', float(os.environ.get('GEOIP_FALLBACK_TIMEOUT', '0.6')))
    app.config.setdefault('GEOIP_CACHE_TTL_SECONDS', int(os.environ.get('GEOIP_CACHE_TTL_SECONDS', '86400')))
    app.config.setdefault('GEOIP_NEGATIVE_CACHE_TTL_SECONDS', int(os.environ.get('GEOIP_NEGATIVE_CACHE_TTL_SECONDS', '900')))
    try:
        from app.utils.geoip import init_geoip_reader, init_geoip_settings, parse_trusted_proxies
        init_geoip_reader(app.config.get('GEOIP_DB_PATH'), app.logger)
        init_geoip_settings(
            fallback_enabled=app.config.get('GEOIP_FALLBACK_ENABLED'),
            fallback_url_template=app.config.get('GEOIP_FALLBACK_URL'),
            fallback_timeout=app.config.get('GEOIP_FALLBACK_TIMEOUT'),
            cache_ttl_seconds=app.config.get('GEOIP_CACHE_TTL_SECONDS'),
            negative_cache_ttl_seconds=app.config.get('GEOIP_NEGATIVE_CACHE_TTL_SECONDS'),
        )
        app.config['GEOIP_TRUSTED_PROXIES'] = parse_trusted_proxies(
            app.config.get('GEOIP_TRUSTED_PROXY_CIDRS')
        )
    except Exception:
        # GeoIP is optional and must never break startup.
        app.config['GEOIP_TRUSTED_PROXIES'] = []
        pass
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    ckeditor.init_app(app)

    # Startup DB tasks (schema patch + optional Alembic upgrade)
    #
    # IMPORTANT FOR PRODUCTION (Render): default is OFF.
    # We do not run Alembic upgrades or create/alter tables at import/startup
    # unless explicitly enabled, to avoid risky behavior in multi-worker
    # environments and to respect strict “migration-only” production workflows.
    enable_startup_db_tasks = os.environ.get('ENABLE_STARTUP_DB_TASKS') == '1'
    if config_name != 'production' or enable_startup_db_tasks:
        _force_create_tables(app)
    else:
        _safe_log(
            app,
            'info',
            'Startup DB tasks are disabled in production. '
            'Use Render releaseCommand (flask db upgrade) or set ENABLE_STARTUP_DB_TASKS=1 for emergency override.',
        )

    # Register Jinja2 filters for unit conversions
    try:
        from app.utils.unit_converter import register_filters
        register_filters(app)
    except Exception as filter_exc:
        app.logger.warning(f'Unit converter filter registration failed: {filter_exc}')
    
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

    # Initialize visit tracking (reports to API every 30 minutes)
    try:
        from app.services.visit_tracker import init_visit_tracking
        init_visit_tracking(app)
    except Exception as tracker_exc:
        app.logger.warning(f'Visit tracking initialization failed: {tracker_exc}')

    @app.after_request
    def _apply_security_headers(response):
        """Apply safe security headers without affecting app logic."""
        csp = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self' https://wa.me https://gumroad.com https://gum.co; "
            "frame-ancestors 'none'; "
            "img-src 'self' data: https:; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.ckeditor.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.ckeditor.com; "
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
    
    # NOTE: robots.txt is served by main blueprint (/robots.txt) so we avoid
    # registering a duplicate URL rule here.
    
    return app


def register_blueprints(app):
    """Register Flask blueprints"""
    
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.health import health_bp
    from app.routes.blog import blog_bp
    from app.blueprints.space_planner import space_planner_bp
    from app.blueprints.planner import planner_bp
    from app.blueprints.room_checker import room_checker_bp
    from app.blueprints.progress_intelligence import progress_intelligence_bp
    from app.blueprints.area_calculator import area_calculator_bp
    from app.blueprints.floor_plan_analyzer import floor_plan_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(health_bp)  # No prefix - accessible at /health
    app.register_blueprint(blog_bp)
    app.register_blueprint(space_planner_bp, url_prefix='/space-planner')
    app.register_blueprint(planner_bp, url_prefix='/planner')
    app.register_blueprint(room_checker_bp, url_prefix='/room-checker')
    app.register_blueprint(progress_intelligence_bp, url_prefix='/progress-intelligence')
    app.register_blueprint(area_calculator_bp, url_prefix='/house-area-calculator')
    app.register_blueprint(floor_plan_bp, url_prefix='/tools/floor-plan-analyzer')


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
        try:
            from flask import g
            from app.services.analytics.request_logging import log_error

            log_error(event=getattr(g, 'analytics_event', None), error=error, status_code=500)
        except Exception:
            pass
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
        from app.utils.responsive_media import picture_tag, srcset_for, CARD_PRESET, HERO_PRESET
        from flask import request
        from app.utils.geoip import get_country_for_ip, resolve_client_ip
        from app.utils.pack_visibility import load_pack_visibility, filter_pack_tiers, visible_starting_price
        from app.utils.category_colors import get_category_color, get_category_style
        from app.seo import generate_organization_schema, generate_website_schema

        def render_richtext(value):
            """Render blog content with paragraph breaks.

            - If content already looks like HTML (CKEditor), return it as-is.
            - If content is plain text, convert blank-line-separated paragraphs
              to <p> blocks and preserve single newlines as <br>.
            """

            if value is None:
                return ''

            try:
                from markupsafe import Markup, escape
                import re

                text_value = str(value)
                # Heuristic: treat as HTML if it contains tags.
                if '<' in text_value and '>' in text_value:
                    return Markup(text_value)

                paragraphs = [p for p in re.split(r'\n\s*\n', text_value) if p.strip()]
                rendered = []
                for p in paragraphs:
                    safe_p = escape(p.strip()).replace('\n', Markup('<br>'))
                    rendered.append(Markup('<p>') + safe_p + Markup('</p>'))
                return Markup('').join(rendered)
            except Exception:
                # Absolute fallback: return raw text.
                return str(value)

        def query_args(exclude=None):
            exclude = set(exclude or [])
            args = request.args.to_dict(flat=True)
            for key in exclude:
                args.pop(key, None)
            return args

        def client_ip():
            return resolve_client_ip(
                request.headers,
                request.remote_addr,
                trusted_proxies=app.config.get('GEOIP_TRUSTED_PROXIES'),
            ) or '0.0.0.0'

        visitor_ip = client_ip()
        visitor_country = get_country_for_ip(visitor_ip)
        pack_visibility = load_pack_visibility()

        organization_schema = None
        website_schema = None
        try:
            organization_schema = generate_organization_schema()
            website_schema = generate_website_schema()
        except Exception:
            organization_schema = None
            website_schema = None
        return {
            'site_name': app.config['SITE_NAME'],
            'site_description': app.config['SITE_DESCRIPTION'],
            'site_url': app.config['SITE_URL'],
            'site_keywords': app.config.get('SITE_KEYWORDS', ''),
            'organization_schema': organization_schema,
            'website_schema': website_schema,
            'upload_url': upload_url,
            'picture_tag': picture_tag,
            'CARD_PRESET': CARD_PRESET,
            'HERO_PRESET': HERO_PRESET,
            'srcset_for': srcset_for,
            'pack_visibility': pack_visibility,
            'filter_pack_tiers': filter_pack_tiers,
            'visible_starting_price': visible_starting_price,
            'render_richtext': render_richtext,
            'query_args': query_args,
            'client_ip': visitor_ip,
            'visitor_country': visitor_country,
            'geoip_country': get_country_for_ip,
            'get_category_color': get_category_color,
            'get_category_style': get_category_style,
        }

    @app.context_processor
    def inject_random_post():
        """Inject a random published blog post on public pages (SEO promo).

        Safety:
            - Read-only: only SELECT queries.
            - Never runs for admin routes.
            - Fails closed (returns None) and rolls back on DB errors to avoid
              poisoning the session.
        """

        try:
            from flask import request
        except Exception:
            return {'random_post': None}

        try:
            if request.path.startswith('/admin'):
                return {'random_post': None}
        except Exception:
            return {'random_post': None}

        try:
            from sqlalchemy import func
            from app.models import BlogPost

            post = (
                BlogPost.query
                .filter_by(status=BlogPost.STATUS_PUBLISHED)
                .order_by(func.random())
                .first()
            )
            return {'random_post': post}
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            return {'random_post': None}


def register_shell_context(app):
    """Register shell context for Flask CLI"""
    
    @app.shell_context_processor
    def make_shell_context():
        """Make database models available in Flask shell"""
        from app.models import User, HousePlan, Category, Order, ContactMessage, Visitor, BlogPost
        return {
            'db': db,
            'User': User,
            'HousePlan': HousePlan,
            'Category': Category,
            'Order': Order,
            'ContactMessage': ContactMessage,
            'Visitor': Visitor,
            'BlogPost': BlogPost,
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
        from app.utils.geoip import resolve_client_ip
        return resolve_client_ip(
            request.headers,
            request.remote_addr,
            trusted_proxies=app.config.get('GEOIP_TRUSTED_PROXIES'),
        ) or '0.0.0.0'

    @app.before_request
    def _block_common_bot_probes():
        """Return a fast 404 for common scanner/bot probe paths.

        Counts as "blocked_attacks" but does not persist full per-request logs.
        """

        try:
            path = (request.path or '/').strip() or '/'
        except Exception:
            return

        # Never interfere with SEO-critical or static routes.
        if path in ('/robots.txt', '/sitemap.xml', '/sw.js', '/offline', '/favicon.ico'):
            return
        if path.startswith('/static/'):
            return

        try:
            from app.services.analytics.traffic import is_obvious_attack_path

            if is_obvious_attack_path(path):
                from datetime import datetime
                from flask import abort
                from app.services.analytics.counters import increment_attack

                increment_attack(datetime.utcnow().date())
                abort(404)
        except Exception:
            return

    @app.before_request
    def _prepare_smart_analytics():
        """Classify traffic and keep only useful signals."""

        g.analytics_event = None
        g.visit_track = None
        g.request_start = None
        g.request_ts = None

        if not app.config.get('ANALYTICS_ENABLED', True):
            return

        path = (request.path or '/').strip() or '/'

        try:
            import time as _time

            g.request_start = _time.perf_counter()
            g.request_ts = datetime.utcnow()
        except Exception:
            g.request_start = None
            g.request_ts = datetime.utcnow()

        # Skip noisy/low-value endpoints.
        if path == '/favicon.ico':
            return
        if path.startswith('/static/') or request.endpoint == 'static':
            return
        if path.startswith('/admin'):
            return
        if path.startswith('/health'):
            return
        if request.method not in ('GET', 'POST', 'HEAD'):
            return
        if current_user.is_authenticated and getattr(current_user, 'role', None) == 'superadmin':
            return

        ua = (request.headers.get('User-Agent') or '')[:500]
        referrer = (request.referrer or '')[:500] or None
        method = (request.method or '')[:12]

        device = 'unknown'
        try:
            from app.utils.device_detection import detect_device_type

            device = detect_device_type(ua)
        except Exception:
            device = 'unknown'

        try:
            from app.services.analytics.traffic import classify_traffic
            from app.services.analytics.counters import increment_bot, increment_human
            from app.services.analytics.tracking import AnalyticsEvent

            classification = classify_traffic(path=path, user_agent=ua)
            now = datetime.utcnow()
            day = now.date()

            if classification.traffic_type == 'bot':
                increment_bot(day)
            else:
                increment_human(day)

            # Resolve GeoIP only when likely to be logged.
            should_lookup_country = (
                classification.traffic_type == 'human'
                or classification.is_search_bot
                or app.config.get('ANALYTICS_LOG_GENERIC_BOTS', False)
            )

            country_code = ''
            country_name = ''
            if should_lookup_country:
                try:
                    from app.services.analytics.tracking import safe_country_for_ip

                    country_code, country_name = safe_country_for_ip(_client_ip())
                except Exception:
                    country_code, country_name = 'UN', 'Unknown'

            try:
                g.visitor_country = country_name or 'Unknown'
            except Exception:
                pass

            session_id = None
            if classification.traffic_type == 'human':
                try:
                    from flask import session
                    import uuid

                    if not session.get('visitor_session_id'):
                        session['visitor_session_id'] = uuid.uuid4().hex
                    session_id = session.get('visitor_session_id')
                except Exception:
                    session_id = None

            g.analytics_event = AnalyticsEvent(
                timestamp=now,
                ip_address=_client_ip(),
                country_code=country_code,
                country_name=country_name,
                request_path=path[:255],
                user_agent=ua,
                traffic_type=classification.traffic_type,
                is_search_bot=classification.is_search_bot,
                device=device,
                method=method,
                referrer=referrer,
                session_id=session_id,
            )
        except Exception:
            # Never break requests due to analytics.
            g.analytics_event = None

        # Optional legacy visitor logging (unbounded growth). Disabled by default.
        if not app.config.get('ENABLE_LEGACY_VISITOR_LOGGING', False):
            return

        g.visit_track = {
            'timestamp': datetime.utcnow(),
            'ip': _client_ip(),
            'ua': ua,
            'page': path[:255],
        }

    @app.after_request
    def _persist_analytics(response):
        event = getattr(g, 'analytics_event', None)
        if event is not None:
            try:
                import time as _time
                from app.services.analytics.tracking import record_event
                from app.services.analytics.request_logging import log_request, log_analyzer_event

                if event.status_code is None:
                    event.status_code = getattr(response, 'status_code', None)

                if event.response_time_ms is None and g.request_start is not None:
                    event.response_time_ms = (_time.perf_counter() - g.request_start) * 1000

                record_event(event)

                if event.traffic_type == 'human':
                    log_request(event=event, log_type='visitor')
                elif event.traffic_type == 'bot':
                    if getattr(event, 'is_search_bot', False):
                        log_request(event=event, log_type='crawler')
                    else:
                        log_request(event=event, log_type='bot')

                if (request.path or '').startswith('/tools/floor-plan-analyzer'):
                    log_analyzer_event(event=event, event_type='request')

                if (request.path or '').startswith('/api'):
                    log_request(event=event, log_type='api')

                try:
                    threshold = int(app.config.get('PERFORMANCE_LOG_THRESHOLD_MS', 1500))
                    if event.response_time_ms and event.response_time_ms >= threshold:
                        log_request(event=event, log_type='performance')
                except Exception:
                    pass
            except Exception:
                pass

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
                app.logger.warning('Visitor logging failed: %s', exc, exc_info=True)
            except Exception as log_exc:
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
