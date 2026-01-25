"""ImmoCash Smart Floor Plan Analyzer blueprint."""

from flask import Blueprint

floor_plan_bp = Blueprint(
    'floor_plan',
    __name__,
    url_prefix='/tools/floor-plan-analyzer',
    template_folder='templates',
    static_folder='static'
)

from . import routes
