from __future__ import annotations

from typing import Dict, Optional

from flask import flash, redirect, render_template, request, url_for

from app.seo import generate_meta_tags
from app.utils.experience_links import article_for_space_planner
from app.domain.spatial_validation import validate_room_dimensions

from . import planner_bp
from .data import ITEMS, ROOMS, ItemSpec, RoomSpec
from .logic import UNITS, FitAnalysis, UnitSystem, evaluate_fit, from_cm, to_cm
from .recommendations import Recommendation, build_invalid_room_recommendation, build_recommendation


def _parse_positive_number(value: str, field_name: str, *, flash_errors: bool) -> Optional[float]:
    raw = (value or '').strip().replace(',', '.')
    if not raw:
        if flash_errors:
            flash(f"Please enter {field_name}.", 'warning')
        return None

    try:
        num = float(raw)
    except ValueError:
        if flash_errors:
            flash(f"{field_name} must be a number.", 'warning')
        return None

    if num <= 0:
        if flash_errors:
            flash(f"{field_name} must be greater than 0.", 'warning')
        return None

    return num


def _room_list():
    return sorted(ROOMS.values(), key=lambda r: r.label)


def _items_for_room(room: RoomSpec) -> Dict[str, ItemSpec]:
    return {k: ITEMS[k] for k in room.item_keys if k in ITEMS}


def _fmt_units_value(value: float) -> str:
    return f"{value:.2f}".rstrip('0').rstrip('.')


def _micro_tool_link(
    *,
    room_slug: str,
    units: UnitSystem,
    room_length: str,
    room_width: str,
    item_key: str,
    item_length: str,
    item_width: str,
) -> str:
    return url_for(
        'planner.room',
        room_slug=room_slug,
        units=units.key,
        room_length=room_length,
        room_width=room_width,
        item_key=item_key,
        item_length=item_length,
        item_width=item_width,
    )


def _build_micro_tools(
    *,
    room: RoomSpec,
    units: UnitSystem,
    room_items: Dict[str, ItemSpec],
    current_item_key: str,
    room_length: str,
    room_width: str,
) -> list[dict]:
    """Curiosity-driven helpers to encourage exploration.

    Must be short, friendly, and context-aware (room + item + entered dimensions).
    """

    def _item_link(item_key: str, *, override_cm: tuple[float, float] | None = None) -> str:
        it = room_items.get(item_key) or ITEMS.get(item_key)
        if it is None:
            return url_for('planner.room', room_slug=room.slug)
        if override_cm is None:
            l = _fmt_units_value(from_cm(it.default_length_cm, units.key))
            w = _fmt_units_value(from_cm(it.default_width_cm, units.key))
        else:
            l = _fmt_units_value(from_cm(override_cm[0], units.key))
            w = _fmt_units_value(from_cm(override_cm[1], units.key))

        return _micro_tool_link(
            room_slug=room.slug,
            units=units,
            room_length=room_length,
            room_width=room_width,
            item_key=item_key,
            item_length=l,
            item_width=w,
        )

    tools: list[dict] = []

    # Room-specific “try next” prompts
    if room.slug == 'kitchen':
        tools.append({
            'tone': 'info',
            'icon': 'fa-solid fa-utensils',
            'title': 'Can you use appliances comfortably?',
            'body': 'Try another kitchen item to see if daily cooking still feels comfortable for daily use.',
            'cta': 'Test a dishwasher',
            'href': _item_link('dishwasher'),
        })

    elif room.slug in {'bedroom', 'master-bedroom', 'children-room'}:
        # Pick something different from the current choice.
        pick = 'wardrobe' if current_item_key.startswith('bed_') else 'bed_queen'
        tools.append({
            'tone': 'info',
            'icon': 'fa-solid fa-bed',
            'title': 'Want a better layout option?',
            'body': 'Quick check: switch the item and see which setup feels more comfortable for daily use.',
            'cta': 'Check a wardrobe fit',
            'href': _item_link(pick),
        })

    elif room.slug == 'living-room':
        tools.append({
            'tone': 'info',
            'icon': 'fa-solid fa-couch',
            'title': 'Is your sofa too big?',
            'body': 'Try a slightly smaller sofa size and compare how open the room feels for daily use.',
            'cta': 'Try a smaller sofa',
            'href': _item_link('sofa', override_cm=(180, 85)),
        })

    elif room.slug in {'bathroom', 'wc'}:
        tools.append({
            'tone': 'info',
            'icon': 'fa-solid fa-bath',
            'title': 'Will daily use feel comfortable?',
            'body': 'Bathrooms are all about ease of use. Try another item to see what feels best long-term.',
            'cta': 'Test a shower',
            'href': _item_link('shower') if 'shower' in ITEMS else url_for('planner.room', room_slug=room.slug),
        })

    elif room.slug == 'office':
        tools.append({
            'tone': 'info',
            'icon': 'fa-solid fa-laptop',
            'title': 'Does working feel easy?',
            'body': 'Try a desk layout and see if it stays comfortable for daily use when sitting and moving around.',
            'cta': 'Test a desk',
            'href': _item_link('desk'),
        })

    elif room.slug == 'garage':
        tools.append({
            'tone': 'info',
            'icon': 'fa-solid fa-warehouse',
            'title': 'Can you still move around?',
            'body': 'Try storage vs vehicle and see which layout is more comfortable for daily use.',
            'cta': 'Test storage shelves',
            'href': _item_link('storage_shelves'),
        })

    else:
        tools.append({
            'tone': 'info',
            'icon': 'fa-solid fa-wand-magic-sparkles',
            'title': 'Try a different item',
            'body': 'Small changes can create a better layout option quickly.',
            'cta': 'Pick another item',
            'href': url_for('planner.room', room_slug=room.slug),
        })

    # Always include a gentle exploration CTA
    tools.append({
        'tone': 'neutral',
        'icon': 'fa-solid fa-compass',
        'title': 'Explore another room',
        'body': 'Curious? Try one more room and compare comfort in seconds.',
        'cta': 'Browse rooms',
        'href': url_for('planner.index'),
    })

    return tools[:2]


@planner_bp.get('')
@planner_bp.get('/')
def index():
    learn_article = article_for_space_planner(intent='furniture-fit', room_slug=None)
    meta = generate_meta_tags(
        title='Room Planner',
        description='A human-friendly room planner that helps you check if furniture and appliances will feel comfortable in a space.',
        url=url_for('planner.index', _external=True),
    )

    return render_template('planner/index.html', rooms=_room_list(), learn_article=learn_article, meta=meta)


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

    micro_tools = _build_micro_tools(
        room=room_spec,
        units=units,
        room_items=room_items,
        current_item_key=item_key,
        room_length=form['room_length'],
        room_width=form['room_width'],
    )

    learn_article = article_for_space_planner(intent='furniture-fit', room_slug=room_spec.slug)

    # Compute results on POST, and also on GET when a share link includes all params.
    should_compute = request.method == 'POST'
    if not should_compute:
        required_fields = ('room_length', 'room_width', 'item_length', 'item_width', 'item_key')
        should_compute = all((request.values.get(k) or '').strip() for k in required_fields)

    if should_compute:
        flash_errors = request.method == 'POST'
        room_length = _parse_positive_number(form['room_length'], f"room length ({units.length_label})", flash_errors=flash_errors)
        room_width = _parse_positive_number(form['room_width'], f"room width ({units.length_label})", flash_errors=flash_errors)
        item_length = _parse_positive_number(
            form['item_length'],
            f"{item.label.lower()} length ({units.length_label})" if item else f"item length ({units.length_label})",
            flash_errors=flash_errors,
        )
        item_width = _parse_positive_number(
            form['item_width'],
            f"{item.label.lower()} width ({units.length_label})" if item else f"item width ({units.length_label})",
            flash_errors=flash_errors,
        )

        if item is None and flash_errors:
            flash('Please choose an item.', 'warning')

        if all(v is not None for v in (room_length, room_width, item_length, item_width)) and item is not None:
            room_length_cm = to_cm(room_length, units.key)
            room_width_cm = to_cm(room_width, units.key)
            item_length_cm = to_cm(item_length, units.key)
            item_width_cm = to_cm(item_width, units.key)

            validation = validate_room_dimensions(
                room_slug=room_spec.slug,
                room_label=room_spec.label,
                length_m=(room_length_cm / 100.0),
                width_m=(room_width_cm / 100.0),
                units_key=units.key,
            )

            if not validation.ok:
                rec = build_invalid_room_recommendation(room=room_spec, item=item, reason=validation.reason)
                analysis = None
            else:
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
                    if flash_errors:
                        flash('Something went wrong. Please double-check your inputs.', 'danger')

    page_title = f"Room Planner — {room_spec.label}"
    page_desc = f"Check if furniture fits comfortably in a {room_spec.label.lower()}."
    if rec and item:
        page_title = f"{rec.verdict} — {room_spec.label} — {item.label}"
        page_desc = f"{rec.verdict}: {rec.seo_line}"

    meta = generate_meta_tags(
        title=page_title,
        description=page_desc,
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
        micro_tools=micro_tools,
        learn_article=learn_article,
        meta=meta,
    )
