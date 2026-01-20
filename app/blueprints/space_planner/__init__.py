"""Space Planner (Furniture Fit & Space Planning Assistant) blueprint."""

from flask import Blueprint

space_planner_bp = Blueprint(
    'space_planner',
    __name__,
)

# Import routes to register view functions
from . import routes  # noqa: E402,F401
