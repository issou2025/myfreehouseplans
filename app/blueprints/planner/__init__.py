"""Planner blueprint: complete room + furniture/appliance fit assistant."""

from flask import Blueprint

planner_bp = Blueprint('planner', __name__)

from . import routes  # noqa: E402,F401
