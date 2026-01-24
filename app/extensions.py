"""
Flask Extensions Module

This module initializes all Flask extensions used in the application.
Extensions are initialized here and then attached to the app in the factory.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_limiter import Limiter
from flask_ckeditor import CKEditor


def _rate_limit_key() -> str:
	"""Best-effort client IP key for rate limiting.

	Uses proxy-aware resolution when a request context exists.
	Falls back to remote_addr if resolution fails.
	"""

	try:
		from flask import current_app, has_request_context, request

		if not has_request_context():
			return '0.0.0.0'

		from app.utils.geoip import resolve_client_ip

		resolved = resolve_client_ip(
			request.headers,
			request.remote_addr,
			trusted_proxies=current_app.config.get('GEOIP_TRUSTED_PROXIES'),
		)
		return resolved or (request.remote_addr or '0.0.0.0')
	except Exception:
		try:
			from flask import request

			return request.remote_addr or '0.0.0.0'
		except Exception:
			return '0.0.0.0'

# Initialize extensions
# These will be attached to the app in create_app()
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
limiter = Limiter(key_func=_rate_limit_key)
ckeditor = CKEditor()

# Configure login manager
login_manager.login_view = 'admin.admin_login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'
login_manager.session_protection = 'strong'
