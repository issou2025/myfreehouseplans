from __future__ import annotations

from typing import Optional

from flask import redirect, flash, render_template, request, url_for

from app.seo import generate_meta_tags

from . import room_checker_bp
from .data import ROOMS, ROOM_ORDER, RoomType
from .logic import UNITS, RoomSizeInputs, UnitSystem, evaluate_room_quality
from .recommendations import Recommendation, build_recommendation


def _parse_positive(value: str) -> Optional[float]:
    raw = (value or '').strip().replace(',', '.')
    if not raw:
        return None
    try:
        num = float(raw)
    except ValueError:
        return None
    if num <= 0:
        return None
    return num


def _room_list():
    out = []
    for slug in ROOM_ORDER:
        rt = ROOMS.get(slug)
        if rt:
            out.append(rt)
    # include any future rooms not in the curated order
    for slug, rt in sorted(ROOMS.items(), key=lambda kv: kv[1].label):
        if rt not in out:
            out.append(rt)
    return out


def _build_micro_tools(*, room: RoomType) -> list[dict]:
    # Always: send to the Room Planner (furniture) for the same room when available.
    planner_slug = room.slug
    tools = [
        {
            'tone': 'info',
            'icon': 'fa-solid fa-ruler-combined',
            'title': 'Want to go deeper?',
            'body': 'Try the Room Planner to check if furniture and appliances feel comfortable in this room.',
            'cta': 'Open Room Planner',
            'href': url_for('planner.room', room_slug=planner_slug),
        },
        {
            'tone': 'neutral',
            'icon': 'fa-solid fa-compass',
            'title': 'Check another room type',
            'body': 'One more quick check can reveal a better layout option.',
            'cta': 'Browse room checks',
            'href': url_for('room_checker.index'),
        },
    ]
    return tools


@room_checker_bp.route('', methods=['GET', 'POST'])
@room_checker_bp.route('/', methods=['GET', 'POST'])
def index():
    # Repositioning: keep legacy URL working, but make the Space Planner URL canonical.
    # - GET: 301 redirect (share links preserved)
    # - POST: 302 redirect (turn form submit into a shareable URL)
    if request.method == 'GET':
        params = {k: v for k, v in request.args.items() if v}
        return redirect(url_for('space_planner.room_size', **params), code=301)
    if request.method == 'POST':
        params = {k: v for k, v in request.form.items() if v}
        return redirect(url_for('space_planner.room_size', **params), code=302)

    room_slug = (request.values.get('room') or '').strip()
    room = ROOMS.get(room_slug) if room_slug else None

    # Support both `units` (current) and `unit` (legacy/share links)
    unit_key = (request.values.get('units') or request.values.get('unit') or 'metric').strip().lower()
    units: UnitSystem = UNITS.get(unit_key, UNITS['metric'])

    # Support both `method` (current) and `mode` (legacy/share links)
    method = (request.values.get('method') or request.values.get('mode') or 'dims').strip().lower()
    if method in {'dimensions', 'dimension', 'lengthwidth', 'length_width', 'lw'}:
        method = 'dims'
    if method not in {'dims', 'area'}:
        method = 'dims'

    form = {
        'room': room_slug,
        'units': units.key,
        'method': method,
        'length': request.values.get('length', ''),
        'width': request.values.get('width', ''),
        'area': request.values.get('area', ''),
        # Optional helpers (area mode): allow one side to infer the other internally
        'area_length': request.values.get('area_length', ''),
        'area_width': request.values.get('area_width', ''),
    }

    rec: Optional[Recommendation] = None

    should_compute = request.method == 'POST'
    if not should_compute:
        # Share links: compute when we have enough info
        if room_slug and room and method == 'dims':
            should_compute = bool(form['length'].strip() and form['width'].strip())
        elif room_slug and room and method == 'area':
            should_compute = bool(form['area'].strip())

    if should_compute:
        if room is None:
            flash('Please choose a room type.', 'warning')
        else:
            try:
                if method == 'dims':
                    length = _parse_positive(form['length'])
                    width = _parse_positive(form['width'])
                    if length is None or width is None:
                        if request.method == 'POST':
                            flash('Please enter a valid length and width.', 'warning')
                    else:
                        result = evaluate_room_quality(
                            room=room,
                            inputs=RoomSizeInputs(method='dims', length=length, width=width),
                            units_key=units.key,
                        )
                        rec = build_recommendation(room=room, result=result)

                else:
                    area = _parse_positive(form['area'])
                    # Optional side hints (kept invisible in output; used only for shape note)
                    area_len = _parse_positive(form['area_length'])
                    area_wid = _parse_positive(form['area_width'])

                    if area is None:
                        if request.method == 'POST':
                            flash('Please enter a valid total surface.', 'warning')
                    else:
                        result = evaluate_room_quality(
                            room=room,
                            inputs=RoomSizeInputs(method='area', area=area, length=area_len, width=area_wid),
                            units_key=units.key,
                        )
                        rec = build_recommendation(room=room, result=result)
            except Exception:
                if request.method == 'POST':
                    flash('Something went wrong. Please double-check your inputs.', 'danger')

    title = 'Room Size & Quality Checker'
    desc = 'Check whether a room feels comfortable, acceptable, or not recommended based on size — in plain language.'
    if room and rec:
        title = f"{rec.verdict} — {room.label} size"
        desc = rec.seo_line

    meta = generate_meta_tags(
        title=title,
        description=desc,
        url=url_for('room_checker.index', _external=True),
    )

    micro_tools = _build_micro_tools(room=room) if room else []

    return render_template(
        'room_checker/index.html',
        rooms=_room_list(),
        room=room,
        units=units,
        unit_options=list(UNITS.values()),
        form=form,
        recommendation=rec,
        micro_tools=micro_tools,
        meta=meta,
    )
