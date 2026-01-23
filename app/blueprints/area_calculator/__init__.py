"""International House Area & Space Calculator blueprint."""

from flask import Blueprint

area_calculator_bp = Blueprint(
    'area_calculator',
    __name__,
    template_folder='../../templates',
)

from . import routes  # noqa: E402,F401
