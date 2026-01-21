"""Progress Intelligence blueprint (construction progress simulation)."""

from flask import Blueprint

progress_intelligence_bp = Blueprint('progress_intelligence', __name__)

from . import routes  # noqa: E402,F401
