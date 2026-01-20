from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from flask import flash, render_template, request, url_for

from app.seo import generate_meta_tags

from . import space_planner_bp
from .logic import FitAnalysis, FurnitureType, evaluate_fit, get_furniture_catalog
from .recommendations import Recommendation, build_recommendation


@dataclass(frozen=True)
class RoomType:
    slug: str
    label: str
    description: str
    icon: str
    allowed_furniture_keys: Tuple[str, ...]


ROOMS: Dict[str, RoomType] = {
    'bedroom': RoomType(
        slug='bedroom',
        label='Bedroom',
        description='Beds and wardrobes with proper access clearances.',
        icon='fa-solid fa-bed',
        allowed_furniture_keys=('bed', 'wardrobe', 'table'),
    ),
    'living-room': RoomType(
        slug='living-room',
        label='Living Room',
        description='Sofas and tables with comfortable circulation.',
        icon='fa-solid fa-couch',
        allowed_furniture_keys=('sofa', 'table'),
    ),
    'kitchen': RoomType(
        slug='kitchen',
        label='Kitchen',
        description='Dining table fit check with realistic pull-out space.',
        icon='fa-solid fa-utensils',
        allowed_furniture_keys=('table',),
    ),
    'bathroom': RoomType(
        slug='bathroom',
        label='Bathroom',
        description='Shower and WC clearances for functional use.',
        icon='fa-solid fa-bath',
        allowed_furniture_keys=('shower', 'wc'),
    ),
    'wc': RoomType(
        slug='wc',
        label='WC',
        description='Quick check for WC functional clearance.',
        icon='fa-solid fa-toilet',
        allowed_furniture_keys=('wc',),
    ),
}


def _parse_positive_cm(value: str, field_name: str) -> Optional[float]:
    """Parse a user number as centimeters."""

    raw = (value or '').strip().replace(',', '.')
    if not raw:
        flash(f"Please enter {field_name}.", 'warning')
        return None

    try:
        cm = float(raw)
    except ValueError:
        flash(f"{field_name} must be a number.", 'warning')
        return None

    if cm <= 0:
        flash(f"{field_name} must be greater than 0.", 'warning')
        return None

    # Practical bounds to prevent accidental unit mistakes.
    if cm < 30 or cm > 5000:
        flash(f"{field_name} looks unusual. Please enter centimeters (cm).", 'warning')
        return None

    return cm


def _furniture_options_for(room: RoomType, catalog: Dict[str, FurnitureType]):
    options = [catalog[k] for k in room.allowed_furniture_keys if k in catalog]
    # stable, user-friendly ordering by label
    return sorted(options, key=lambda f: f.label)


@space_planner_bp.get('')
@space_planner_bp.get('/')
def index():
    meta = generate_meta_tags(
        title='Space Planner',
        description='Check furniture fit and circulation in a room — like an architect, without the calculations.',
        url=url_for('space_planner.index', _external=True),
    )

    rooms = list(ROOMS.values())

    return render_template('space_planner/index.html', rooms=rooms, meta=meta)


@space_planner_bp.route('/bedroom', methods=['GET', 'POST'], defaults={'room_slug': 'bedroom'})
@space_planner_bp.route('/living-room', methods=['GET', 'POST'], defaults={'room_slug': 'living-room'})
@space_planner_bp.route('/kitchen', methods=['GET', 'POST'], defaults={'room_slug': 'kitchen'})
@space_planner_bp.route('/bathroom', methods=['GET', 'POST'], defaults={'room_slug': 'bathroom'})
@space_planner_bp.route('/wc', methods=['GET', 'POST'], defaults={'room_slug': 'wc'})
@space_planner_bp.route('/<room_slug>', methods=['GET', 'POST'])
def room(room_slug: str):
    room_type = ROOMS.get(room_slug)
    if room_type is None:
        flash('Unknown room type.', 'warning')
        return render_template('space_planner/index.html', rooms=list(ROOMS.values()))

    catalog = get_furniture_catalog()
    furniture_options = _furniture_options_for(room_type, catalog)

    # Defaults
    form_data = {
        'room_length_cm': request.form.get('room_length_cm', ''),
        'room_width_cm': request.form.get('room_width_cm', ''),
        'furniture_key': request.form.get('furniture_key', furniture_options[0].key if furniture_options else ''),
        'furniture_length_cm': request.form.get('furniture_length_cm', ''),
        'furniture_width_cm': request.form.get('furniture_width_cm', ''),
    }

    analysis: Optional[FitAnalysis] = None
    rec: Optional[Recommendation] = None

    if request.method == 'POST':
        room_length_cm = _parse_positive_cm(form_data['room_length_cm'], 'room length')
        room_width_cm = _parse_positive_cm(form_data['room_width_cm'], 'room width')
        furniture_length_cm = _parse_positive_cm(form_data['furniture_length_cm'], 'furniture length')
        furniture_width_cm = _parse_positive_cm(form_data['furniture_width_cm'], 'furniture width')

        furniture_key = (form_data['furniture_key'] or '').strip()
        furniture = catalog.get(furniture_key)

        if furniture is None:
            flash('Please select a furniture type.', 'warning')
        elif furniture_key not in room_type.allowed_furniture_keys:
            flash('That furniture type is not typical for this room, but we can still check it.', 'info')

        if all(v is not None for v in (room_length_cm, room_width_cm, furniture_length_cm, furniture_width_cm)) and furniture is not None:
            try:
                analysis = evaluate_fit(
                    room_length_cm=room_length_cm,
                    room_width_cm=room_width_cm,
                    furniture=furniture,
                    furniture_length_cm=furniture_length_cm,
                    furniture_width_cm=furniture_width_cm,
                )
                rec = build_recommendation(analysis)
            except Exception:
                flash('Something went wrong while checking fit. Please verify your inputs.', 'danger')

    meta = generate_meta_tags(
        title=f"Space Planner — {room_type.label}",
        description=f"Check {room_type.label.lower()} furniture fit with professional clearances.",
        url=url_for('space_planner.room', room_slug=room_type.slug, _external=True),
    )

    return render_template(
        'space_planner/room.html',
        room=room_type,
        furniture_options=furniture_options,
        form=form_data,
        analysis=analysis,
        recommendation=rec,
        meta=meta,
    )
