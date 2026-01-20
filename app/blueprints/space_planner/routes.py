from __future__ import annotations

from typing import Optional

from flask import flash, redirect, render_template, request, url_for

from app.seo import generate_meta_tags

from app.blueprints.room_checker.data import ROOMS as SIZE_ROOMS, ROOM_ORDER as SIZE_ROOM_ORDER, RoomType
from app.blueprints.room_checker.logic import UNITS, RoomSizeInputs, UnitSystem, evaluate_room_quality

from . import space_planner_bp
from .intent_recommendations import IntentRecommendation, build_intent_recommendation


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
    for slug in SIZE_ROOM_ORDER:
        rt = SIZE_ROOMS.get(slug)
        if rt:
            out.append(rt)
    # include any future rooms not in the curated order
    for slug, rt in sorted(SIZE_ROOMS.items(), key=lambda kv: kv[1].label):
        if rt not in out:
            out.append(rt)
    return out


def _parse_units_and_method():
    # Support both `units` (current) and `unit` (legacy/share links)
    unit_key = (request.values.get('units') or request.values.get('unit') or 'metric').strip().lower()
    units: UnitSystem = UNITS.get(unit_key, UNITS['metric'])

    # Support both `method` (current) and `mode` (legacy/share links)
    method = (request.values.get('method') or request.values.get('mode') or 'dims').strip().lower()
    if method in {'dimensions', 'dimension', 'lengthwidth', 'length_width', 'lw'}:
        method = 'dims'
    if method not in {'dims', 'area'}:
        method = 'dims'

    return units, method


def _intent_shell(
    *,
    intent: str,
    title: str,
    intro: str,
    meta_description: str,
):
    room_slug = (request.values.get('room') or '').strip()
    room: Optional[RoomType] = SIZE_ROOMS.get(room_slug) if room_slug else None

    units, method = _parse_units_and_method()

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

    rec: Optional[IntentRecommendation] = None

    should_compute = request.method == 'POST'
    if not should_compute:
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
                        rec = build_intent_recommendation(intent=intent, room=room, result=result)

                else:
                    area = _parse_positive(form['area'])
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
                        rec = build_intent_recommendation(intent=intent, room=room, result=result)
            except Exception:
                if request.method == 'POST':
                    flash('Something went wrong. Please double-check your inputs.', 'danger')

    # SEO: keep the canonical URL on the Space Planner page.
    meta_title = title
    meta_desc = meta_description
    if room and rec:
        meta_title = f"{rec.verdict} — {room.label}"
        meta_desc = rec.seo_line

    meta = generate_meta_tags(
        title=meta_title,
        description=meta_desc,
        url=request.base_url,
    )

    return render_template(
        'space_planner/intent_tool.html',
        page_title=title,
        page_intro=intro,
        intent=intent,
        rooms=_room_list(),
        room=room,
        units=units,
        unit_options=list(UNITS.values()),
        form=form,
        recommendation=rec,
        meta=meta,
    )


@space_planner_bp.get('')
@space_planner_bp.get('/')
def index():
    meta = generate_meta_tags(
        title='Space Planner',
        description='A human-friendly space planning assistant: room size comfort, furniture fit, circulation, and overall comfort checks.',
        url=url_for('space_planner.index', _external=True),
    )

    return render_template('space_planner/index.html', rooms=_room_list(), meta=meta)


@space_planner_bp.route('/room-size', methods=['GET', 'POST'])
def room_size():
    return _intent_shell(
        intent='room-size',
        title='Space Planner — Room Size',
        intro='Check if a room size will feel comfortable in everyday life (not a technical checklist).',
        meta_description='Room size planner: check whether a room will feel comfortable, tight, or not recommended based on usable space — in plain language.',
    )


@space_planner_bp.route('/circulation', methods=['GET', 'POST'])
def circulation():
    return _intent_shell(
        intent='circulation',
        title='Space Planner — Circulation',
        intro='A quick circulation check: will daily movement feel easy, or will it feel tight?',
        meta_description='Circulation planner: a fast, human-friendly check for movement comfort in a room.',
    )


@space_planner_bp.route('/comfort-check', methods=['GET', 'POST'])
def comfort_check():
    return _intent_shell(
        intent='comfort-check',
        title='Space Planner — Comfort Check',
        intro='An overall comfort check that summarizes how usable the room will feel day-to-day.',
        meta_description='Comfort check: a room usability summary in plain language, with next-step suggestions.',
    )


@space_planner_bp.get('/furniture-fit')
def furniture_fit():
    meta = generate_meta_tags(
        title='Space Planner — Furniture Fit',
        description='Choose a room to check if furniture and appliances fit comfortably with realistic daily-life clearances.',
        url=url_for('space_planner.furniture_fit', _external=True),
    )
    return render_template('space_planner/furniture_fit.html', rooms=_room_list(), meta=meta)


@space_planner_bp.get('/<room_slug>')
def room(room_slug: str):
    room_type: Optional[RoomType] = SIZE_ROOMS.get(room_slug)
    if room_type is None:
        flash('Unknown room type.', 'warning')
        return redirect(url_for('space_planner.index'), code=302)

    meta = generate_meta_tags(
        title=f"{room_type.label} Space Planner",
        description=f"Plan your {room_type.label.lower()} with room size, furniture fit, circulation, and comfort checks.",
        url=url_for('space_planner.room', room_slug=room_type.slug, _external=True),
    )

    return render_template('space_planner/room_overview.html', room=room_type, meta=meta)
