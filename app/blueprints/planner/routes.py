from __future__ import annotations

from typing import Dict, Optional

from flask import flash, redirect, render_template, request, url_for

from app.seo import generate_meta_tags

from . import planner_bp
from .data import ITEMS, ROOMS, ItemSpec, RoomSpec
from .logic import UNITS, FitAnalysis, UnitSystem, evaluate_fit, from_cm, to_cm
from .recommendations import Recommendation, build_recommendation


def _parse_positive_number(value: str, field_name: str) -> Optional[float]:
    raw = (value or '').strip().replace(',', '.')
    if not raw:
        flash(f"Please enter {field_name}.", 'warning')
        return None

    try:
        num = float(raw)
    except ValueError:
        flash(f"{field_name} must be a number.", 'warning')
        return None

    if num <= 0:
        flash(f"{field_name} must be greater than 0.", 'warning')
        return None

    return num


def _room_list():
    return sorted(ROOMS.values(), key=lambda r: r.label)


def _items_for_room(room: RoomSpec) -> Dict[str, ItemSpec]:
    return {k: ITEMS[k] for k in room.item_keys if k in ITEMS}


@planner_bp.get('')
@planner_bp.get('/')
def index():
    meta = generate_meta_tags(
        title='Room Planner',
        description='A human-friendly room planner that helps you check if furniture and appliances will feel comfortable in a space.',
        url=url_for('planner.index', _external=True),
    )

    return render_template('planner/index.html', rooms=_room_list(), meta=meta)


@planner_bp.route('/<room_slug>', methods=['GET', 'POST'])
def room(room_slug: str):
    room_spec = ROOMS.get(room_slug)
    if room_spec is None:
        flash('Unknown room type.', 'warning')
        return redirect(url_for('planner.index'))

    unit_key = (request.values.get('units') or 'metric').strip().lower()
    units: UnitSystem = UNITS.get(unit_key, UNITS['metric'])

    room_items = _items_for_room(room_spec)
    # default item
    default_item_key = next(iter(room_items.keys()), '')

    item_key = (request.values.get('item_key') or default_item_key).strip()
    item = room_items.get(item_key) or (ITEMS.get(item_key) if item_key in ITEMS else None)
    if item is None:
        item_key = default_item_key
        item = room_items.get(item_key)

    # Defaults: prefill with item default dims (converted to chosen unit)
    def _default_val(cm: float) -> str:
        v = from_cm(cm, units.key)
        return f"{v:.2f}".rstrip('0').rstrip('.')

    form = {
        'units': units.key,
        'room_length': request.values.get('room_length', ''),
        'room_width': request.values.get('room_width', ''),
        'item_key': item_key,
        'item_length': request.values.get('item_length', _default_val(item.default_length_cm) if item else ''),
        'item_width': request.values.get('item_width', _default_val(item.default_width_cm) if item else ''),
    }

    analysis: Optional[FitAnalysis] = None
    rec: Optional[Recommendation] = None

    if request.method == 'POST':
        room_length = _parse_positive_number(form['room_length'], f"room length ({units.length_label})")
        room_width = _parse_positive_number(form['room_width'], f"room width ({units.length_label})")
        item_length = _parse_positive_number(form['item_length'], f"{item.label.lower()} length ({units.length_label})" if item else f"item length ({units.length_label})")
        item_width = _parse_positive_number(form['item_width'], f"{item.label.lower()} width ({units.length_label})" if item else f"item width ({units.length_label})")

        if item is None:
            flash('Please choose an item.', 'warning')

        if all(v is not None for v in (room_length, room_width, item_length, item_width)) and item is not None:
            room_length_cm = to_cm(room_length, units.key)
            room_width_cm = to_cm(room_width, units.key)
            item_length_cm = to_cm(item_length, units.key)
            item_width_cm = to_cm(item_width, units.key)

            try:
                analysis = evaluate_fit(
                    room=room_spec,
                    item=item,
                    room_length_cm=room_length_cm,
                    room_width_cm=room_width_cm,
                    item_length_cm=item_length_cm,
                    item_width_cm=item_width_cm,
                )
                rec = build_recommendation(analysis)
            except Exception:
                flash('Something went wrong. Please double-check your inputs.', 'danger')

    meta = generate_meta_tags(
        title=f"Room Planner — {room_spec.label}",
        description=f"Check if furniture fits comfortably in a {room_spec.label.lower()}.",
        url=url_for('planner.room', room_slug=room_spec.slug, _external=True),
    )

    return render_template(
        'planner/room.html',
        room=room_spec,
        units=units,
        unit_options=list(UNITS.values()),
        items=room_items,
        item=item,
        form=form,
        analysis=analysis,
        recommendation=rec,
        meta=meta,
    )
