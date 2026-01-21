"""Reality Check blueprint: decision-prevention system (no costs)."""

from flask import Blueprint

reality_check_bp = Blueprint('reality_check', __name__)

from . import routes  # noqa: E402,F401
