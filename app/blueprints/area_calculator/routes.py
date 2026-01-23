from __future__ import annotations

from typing import Optional

from flask import flash, render_template, request, url_for

from app.domain.area_calculator import CalculatorInput, calculate_house_area
from app.models import BlogPost, HousePlan
from app.seo import generate_meta_tags
from . import area_calculator_bp


@area_calculator_bp.route('/', methods=['GET', 'POST'])
def index():
    """International House Area & Space Calculator."""

    form = {
        'occupants': request.values.get('occupants', '4'),
        'household_type': request.values.get('household_type', 'family'),
        'comfort_level': request.values.get('comfort_level', 'standard'),
        'future_growth': request.values.get('future_growth', 'maybe'),
        'extra_rooms': request.values.getlist('extra_rooms'),
        'land_size': request.values.get('land_size', ''),
        'layout': request.values.get('layout', 'no_preference'),
    }

    result = None
    errors: list[str] = []

    if request.method == 'POST':
        occupants = _parse_int(form['occupants'])
        if occupants is None or occupants < 1 or occupants > 10:
            errors.append('Occupants must be between 1 and 10.')

        land_size = _parse_int(form['land_size'])
        if form['land_size'] and (land_size is None or land_size <= 0):
            errors.append('Land size must be a positive number when provided.')

        if not errors and occupants is not None:
            payload = CalculatorInput(
                occupants=occupants,
                household_type=form['household_type'],
                comfort_level=form['comfort_level'],
                future_growth=form['future_growth'],
                extra_rooms=tuple(form['extra_rooms']),
                land_size=land_size,
                layout=form['layout'],
            )
            result = calculate_house_area(payload)
        else:
            for msg in errors:
                flash(msg, 'warning')

    recommended_plans = _recommended_plans(result)
    recommended_articles = _recommended_articles()

    meta = generate_meta_tags(
        title='House Area Calculator',
        description='International house area calculator that sizes rooms, circulation, and gross area from occupants and lifestyle. Results are explained in plain language.',
        url=url_for('area_calculator.index', _external=True),
    )

    return render_template(
        'area_calculator/house_area.html',
        form=form,
        result=result,
        recommended_plans=recommended_plans,
        recommended_articles=recommended_articles,
        meta=meta,
    )


def _parse_int(value: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _recommended_plans(result):
    try:
        if not result:
            return HousePlan.query.filter_by(is_published=True).order_by(HousePlan.created_at.desc()).limit(6).all()

        target_bedrooms = int(result.summary.get('bedrooms', 0) or 0)
        query = HousePlan.query.filter_by(is_published=True)
        if target_bedrooms > 0:
            query = query.filter(
                (HousePlan.number_of_bedrooms == target_bedrooms) | (HousePlan.bedrooms == target_bedrooms)
            )
        return query.order_by(HousePlan.created_at.desc()).limit(6).all()
    except Exception:
        return []


def _recommended_articles():
    try:
        return (
            BlogPost.query
            .filter_by(status=BlogPost.STATUS_PUBLISHED)
            .order_by(BlogPost.created_at.desc())
            .limit(4)
            .all()
        )
    except Exception:
        return []
