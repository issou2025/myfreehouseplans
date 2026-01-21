from __future__ import annotations

from typing import Optional

from flask import flash, redirect, render_template, request, url_for

from app.seo import generate_meta_tags

from app.blueprints.room_checker.data import ROOMS as SIZE_ROOMS, ROOM_ORDER as SIZE_ROOM_ORDER, RoomType
from app.blueprints.room_checker.logic import UNITS, RoomSizeInputs, UnitSystem, evaluate_room_quality, to_m, to_m2
from app.domain.spatial_validation import validate_room_dimensions
from app.utils.experience_links import article_for_space_planner, room_guidance_line

from . import space_planner_bp
from .intent_recommendations import IntentRecommendation, build_intent_recommendation, build_invalid_intent_recommendation


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


def _split_rooms_for_homepage() -> tuple[list[RoomType], list[RoomType]]:
    """Keep landing pages clean: show a small set of popular rooms first."""

    popular_order = ['bedroom', 'living-room', 'kitchen', 'bathroom', 'office', 'garage']
    by_slug = SIZE_ROOMS
    popular = [by_slug[s] for s in popular_order if s in by_slug]
    popular_slugs = {r.slug for r in popular}
    more = [r for r in _room_list() if r.slug not in popular_slugs]
    return popular, more


def _furniture_fit_quick_actions() -> list[dict]:
    def _href(room_slug: str, *, item_key: str) -> str:
        return url_for('planner.room', room_slug=room_slug, item_key=item_key)

    cards: list[dict] = []
    cards.append({
        'icon': 'fa-solid fa-couch',
        'title': 'Check a sofa and walking space',
        'body': 'Make sure the room still feels easy to move through day-to-day.',
        'cta': 'Test a sectional sofa',
        'href': _href('living-room', item_key='sectional_sofa'),
    })
    cards.append({
        'icon': 'fa-solid fa-chair',
        'title': 'See if a dining table feels usable',
        'body': 'Chairs need room to pull out comfortably — not just “barely fit”.',
        'cta': 'Test a 6-seat table',
        'href': _href('dining-room', item_key='dining_table_6'),
    })
    cards.append({
        'icon': 'fa-solid fa-warehouse',
        'title': 'Check if a car fits in your garage',
        'body': 'Door opening and circulation matter more than you think.',
        'cta': 'Test a car fit',
        'href': _href('garage', item_key='car'),
    })
    cards.append({
        'icon': 'fa-solid fa-route',
        'title': 'Verify hallway / corridor passage',
        'body': 'Keep the space comfortable to walk through every day.',
        'cta': 'Test a console table',
        'href': _href('corridor', item_key='console_table'),
    })
    return cards


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

    learn_article = article_for_space_planner(intent=intent, room_slug=(room.slug if room else None))

    share_text_map = {
        'room-size': 'I checked if this room feels comfortable in real life.',
        'circulation': 'I checked if daily movement will feel comfortable here.',
        'comfort-check': 'I checked the overall comfort of this room for daily life.',
    }
    share_text = share_text_map.get(intent, 'I checked if this space works in real life.')

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
                        validation = validate_room_dimensions(
                            room_slug=room.slug,
                            room_label=room.label,
                            length_m=to_m(length, units.key),
                            width_m=to_m(width, units.key),
                            units_key=units.key,
                        )
                        if not validation.ok:
                            rec = build_invalid_intent_recommendation(intent=intent, room=room, reason=validation.reason)
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
                        area_m2 = to_m2(area, units.key)

                        length_m = None
                        width_m = None
                        if area_len is not None and (area_wid is None):
                            length_m = to_m(area_len, units.key)
                            width_m = (area_m2 / length_m) if (length_m and length_m > 0) else None
                        elif area_wid is not None and (area_len is None):
                            width_m = to_m(area_wid, units.key)
                            length_m = (area_m2 / width_m) if (width_m and width_m > 0) else None
                        elif area_len is not None and area_wid is not None:
                            length_m = to_m(area_len, units.key)
                            width_m = to_m(area_wid, units.key)

                        validation = validate_room_dimensions(
                            room_slug=room.slug,
                            room_label=room.label,
                            length_m=length_m,
                            width_m=width_m,
                            units_key=units.key,
                        )
                        if not validation.ok:
                            rec = build_invalid_intent_recommendation(intent=intent, room=room, reason=validation.reason)
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

    room_hints = {
        r.slug: room_guidance_line(r.slug, r.label)
        for r in _room_list()
    }

    return render_template(
        'space_planner/intent_tool.html',
        page_title=title,
        page_intro=intro,
        intent=intent,
        learn_article=learn_article,
        share_text=share_text,
        rooms=_room_list(),
        room=room,
        room_hints=room_hints,
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
    learn_article = article_for_space_planner(intent='furniture-fit', room_slug=None)
    popular_rooms, more_rooms = _split_rooms_for_homepage()
    suggestions = [
        {
            'icon': 'fa-solid fa-ruler',
            'title': 'Check room size comfort first',
            'body': 'If you’re still choosing dimensions, start with a quick comfort check.',
            'cta': 'Open Room Size',
            'href': url_for('space_planner.room_size'),
        },
        {
            'icon': 'fa-solid fa-heart',
            'title': 'Get an overall comfort signal',
            'body': 'A simple summary of daily-life usability for the room.',
            'cta': 'Open Comfort Check',
            'href': url_for('space_planner.comfort_check'),
        },
    ]

    meta = generate_meta_tags(
        title='Space Planner — Furniture Fit',
        description='Choose a room to check if furniture and appliances fit comfortably with realistic daily-life clearances.',
        url=url_for('space_planner.furniture_fit', _external=True),
    )
    return render_template(
        'space_planner/furniture_fit.html',
        rooms=_room_list(),
        popular_rooms=popular_rooms,
        more_rooms=more_rooms,
        quick_actions=_furniture_fit_quick_actions(),
        suggestions=suggestions,
        learn_article=learn_article,
        meta=meta,
    )


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

    # Prefer a room-specific room-size guide when available.
    learn_article = article_for_space_planner(intent='room-size', room_slug=room_type.slug)

    return render_template('space_planner/room_overview.html', room=room_type, learn_article=learn_article, meta=meta)
