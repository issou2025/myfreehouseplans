"""Room checker blueprint: room size & quality checker (dimension/area based)."""

from flask import Blueprint

room_checker_bp = Blueprint('room_checker', __name__)

from . import routes  # noqa: E402,F401
