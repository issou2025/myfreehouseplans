from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

from flask import current_app, flash, make_response, redirect, render_template, request, url_for

from app.domain.area_calculator import CalculatorInput, calculate_house_area
from app.models import BlogPost, HousePlan
from app.seo import generate_meta_tags
from app.utils.article_extras import load_article_extras, normalize_article_extras
from app.utils.tool_links import resolve_tool_link
from . import area_calculator_bp

UNIT_LABELS = {
    'm2': 'm²',
    'ft2': 'ft²',
}

UNIT_NAMES = {
    'm2': 'square meters',
    'ft2': 'square feet',
}

UNIT_FACTORS = {
    'm2': 1.0,
    'ft2': 10.7639,
}


@area_calculator_bp.route('/', methods=['GET', 'POST'])
def index():
    """Home Space Decision Assistant."""

    form = {
        'occupants': request.values.get('occupants', '4'),
        'household_type': request.values.get('household_type', 'family'),
        'comfort_level': request.values.get('comfort_level', 'standard'),
        'future_growth': request.values.get('future_growth', 'maybe'),
        'extra_rooms': request.values.getlist('extra_rooms'),
        'land_size': request.values.get('land_size', ''),
        'layout': request.values.get('layout', 'no_preference'),
        'unit': request.values.get('unit', 'm2'),
    }

    result = None
    errors: list[str] = []
    unit = _normalize_unit(form.get('unit'))

    if request.method == 'POST':
        occupants = _parse_int(form['occupants'])
        if occupants is None or occupants < 1 or occupants > 10:
            errors.append('Occupants must be between 1 and 10.')

        land_size = _parse_float(form['land_size'])
        if form['land_size'] and (land_size is None or land_size <= 0):
            errors.append('Land size must be a positive number when provided.')

        if not errors and occupants is not None:
            if unit == 'ft2' and land_size:
                land_size = land_size / UNIT_FACTORS['ft2']
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

    tool_key = 'house-area-calculator'
    article_slug = request.args.get('article') or request.args.get('from_article')

    recommended_plans = _recommended_plans(result)
    recommended_articles = _recommended_articles(tool_key=tool_key)
    article_context = _article_context(article_slug, tool_key=tool_key)

    display = _build_display_context(result=result, form=form, unit=unit)
    pdf_url = _build_pdf_url(form=form, unit=unit)

    meta = generate_meta_tags(
        title='Home Space Decision Assistant',
        description='A premium home size decision assistant that sizes rooms, circulation, and gross area in plain language. Built for international households and calm, confident planning.',
        url=url_for('area_calculator.index', _external=True),
    )

    return render_template(
        'area_calculator/house_area.html',
        form=form,
        result=result,
        summary_cards=display.get('summary_cards'),
        land_rows=display.get('land_rows'),
        input_summary=display.get('input_summary'),
        next_steps_display=display.get('next_steps'),
        unit=unit,
        unit_label=display.get('unit_label'),
        unit_name=display.get('unit_name'),
        format_area=display.get('format_area'),
        format_area_value=display.get('format_area_value'),
        pdf_url=pdf_url,
        recommended_plans=recommended_plans,
        recommended_articles=recommended_articles,
        article_context=article_context,
        meta=meta,
    )


@area_calculator_bp.route('/pdf', methods=['GET'])
def pdf():
    """Generate a professional PDF report for the calculator result."""

    form = {
        'occupants': request.args.get('occupants', '4'),
        'household_type': request.args.get('household_type', 'family'),
        'comfort_level': request.args.get('comfort_level', 'standard'),
        'future_growth': request.args.get('future_growth', 'maybe'),
        'extra_rooms': request.args.getlist('extra_rooms'),
        'land_size': request.args.get('land_size', ''),
        'layout': request.args.get('layout', 'no_preference'),
        'unit': request.args.get('unit', 'm2'),
    }

    unit = _normalize_unit(form.get('unit'))
    errors: list[str] = []

    occupants = _parse_int(form['occupants'])
    if occupants is None or occupants < 1 or occupants > 10:
        errors.append('Occupants must be between 1 and 10.')

    land_size = _parse_float(form['land_size'])
    if form['land_size'] and (land_size is None or land_size <= 0):
        errors.append('Land size must be a positive number when provided.')

    if errors or occupants is None:
        for msg in errors:
            flash(msg, 'warning')
        return redirect(url_for('area_calculator.index', **request.args))

    if unit == 'ft2' and land_size:
        land_size = land_size / UNIT_FACTORS['ft2']

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

    display = _build_display_context(result=result, form=form, unit=unit)
    html = render_template(
        'area_calculator/house_area_pdf.html',
        form=form,
        result=result,
        summary_cards=display.get('summary_cards'),
        land_rows=display.get('land_rows'),
        input_summary=display.get('input_summary'),
        next_steps_display=display.get('next_steps'),
        unit=unit,
        unit_label=display.get('unit_label'),
        unit_name=display.get('unit_name'),
        format_area=display.get('format_area'),
        format_area_value=display.get('format_area_value'),
    )

    try:
        from app.services.blog.article_pdf_html import build_article_pdf_weasyprint

        css_path = Path(current_app.static_folder) / 'css' / 'pdf' / 'area_calculator.css'
        pdf_bytes = build_article_pdf_weasyprint(html=html, stylesheets=[css_path])
    except Exception as exc:
        current_app.logger.warning('HTML-to-PDF failed for area calculator: %s', exc)
        pdf_bytes = _fallback_area_pdf_bytes()

    filename = 'home-space-decision-assistant.pdf'
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _parse_int(value: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: str) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_unit(value: Optional[str]) -> str:
    if value == 'ft2':
        return 'ft2'
    return 'm2'


def _format_number(value: Optional[float]) -> str:
    if value is None:
        return '—'
    rounded = round(float(value), 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.1f}"


def _format_area(value: Optional[float], *, factor: float, unit_label: str) -> str:
    if value is None:
        return '—'
    converted = float(value) * factor
    return f"{_format_number(converted)} {unit_label}"


def _format_area_value(value: Optional[float], *, factor: float) -> str:
    if value is None:
        return '—'
    converted = float(value) * factor
    return _format_number(converted)


def _build_display_context(*, result, form, unit: str) -> dict[str, object]:
    unit_label = UNIT_LABELS.get(unit, 'm²')
    unit_name = UNIT_NAMES.get(unit, 'square meters')
    factor = UNIT_FACTORS.get(unit, 1.0)

    def format_area(value: Optional[float]) -> str:
        return _format_area(value, factor=factor, unit_label=unit_label)

    def format_area_value(value: Optional[float]) -> str:
        return _format_area_value(value, factor=factor)

    summary_cards = []
    land_rows = []
    input_summary = []
    next_steps = []

    if result:
        summary_cards = _build_summary_cards_display(result.summary, unit_label=unit_label, factor=factor)
        land_rows = _build_land_rows_display(result.summary, unit_label=unit_label, factor=factor)
        input_summary = _build_input_summary(form, unit_label=unit_label, factor=factor)
        next_steps = _build_next_steps(result.summary, unit_label=unit_label, factor=factor)

    return {
        'unit_label': unit_label,
        'unit_name': unit_name,
        'format_area': format_area,
        'format_area_value': format_area_value,
        'summary_cards': summary_cards,
        'land_rows': land_rows,
        'input_summary': input_summary,
        'next_steps': next_steps,
    }


def _build_summary_cards_display(summary: dict[str, float | int | str | None], *, unit_label: str, factor: float):
    bedrooms = int(summary.get('bedrooms', 0) or 0)
    bathrooms = int(summary.get('bathrooms', 0) or 0)
    net_area = summary.get('net_area')
    gross_area = summary.get('gross_area')
    circulation_ratio = float(summary.get('circulation_ratio', 0.0) or 0.0)

    cards = [
        {
            'label': 'Bedrooms',
            'value': f"{bedrooms}",
            'helper': 'Sleeping rooms sized for your household.',
        },
        {
            'label': 'Bathrooms',
            'value': f"{bathrooms}",
            'helper': 'Full bathrooms; WCs are listed separately.',
        },
        {
            'label': 'Net living area',
            'value': _format_area(net_area, factor=factor, unit_label=unit_label),
            'helper': 'Room-only area before circulation.',
        },
        {
            'label': 'Gross built area',
            'value': _format_area(gross_area, factor=factor, unit_label=unit_label),
            'helper': 'Includes circulation and construction allowance.',
        },
        {
            'label': 'Circulation share',
            'value': f"{int(circulation_ratio * 100)}%",
            'helper': 'Hallways and movement space.',
        },
    ]

    coverage = summary.get('land_coverage')
    if isinstance(coverage, (int, float)):
        cards.append(
            {
                'label': 'Land coverage',
                'value': f"{coverage * 100:.0f}%",
                'helper': 'Estimated footprint share of the site.',
            }
        )

    return cards


def _build_land_rows_display(summary: dict[str, float | int | str | None], *, unit_label: str, factor: float):
    land_size = float(summary.get('land_size', 0) or 0)
    gross_area = float(summary.get('gross_area', 0.0) or 0.0)
    layout = str(summary.get('layout', 'no_preference'))

    if not land_size:
        return [
            {'label': 'Land size provided', 'value': 'Not provided'},
            {'label': 'Footprint estimate', 'value': 'Add land size to evaluate compatibility'},
        ]

    footprint_single = gross_area
    footprint_two = gross_area / 2

    if layout == 'single_storey':
        coverage = footprint_single / land_size
        return [
            {'label': 'Land size', 'value': _format_area(land_size, factor=factor, unit_label=unit_label)},
            {'label': 'Estimated footprint', 'value': _format_area(footprint_single, factor=factor, unit_label=unit_label)},
            {'label': 'Site coverage', 'value': f"{coverage * 100:.0f}%"},
        ]

    if layout == 'two_storey':
        coverage = footprint_two / land_size
        return [
            {'label': 'Land size', 'value': _format_area(land_size, factor=factor, unit_label=unit_label)},
            {'label': 'Estimated footprint', 'value': _format_area(footprint_two, factor=factor, unit_label=unit_label)},
            {'label': 'Site coverage', 'value': f"{coverage * 100:.0f}%"},
        ]

    coverage_single = footprint_single / land_size
    coverage_two = footprint_two / land_size
    return [
        {'label': 'Land size', 'value': _format_area(land_size, factor=factor, unit_label=unit_label)},
        {
            'label': 'Footprint (single-storey)',
            'value': f"{_format_area_value(footprint_single, factor=factor)} {unit_label} · {coverage_single * 100:.0f}%",
        },
        {
            'label': 'Footprint (two-storey)',
            'value': f"{_format_area_value(footprint_two, factor=factor)} {unit_label} · {coverage_two * 100:.0f}%",
        },
    ]


def _build_input_summary(form: dict, *, unit_label: str, factor: float):
    extra_rooms_map = {
        'home_office': 'Home office',
        'guest_room': 'Guest room',
        'storage': 'Storage',
    }
    extra_rooms = [extra_rooms_map.get(key, key) for key in form.get('extra_rooms', [])]
    extra_rooms_text = ', '.join(extra_rooms) if extra_rooms else 'None'

    household_map = {
        'single': 'Single',
        'couple': 'Couple',
        'family': 'Family',
        'extended_family': 'Extended family',
    }
    comfort_map = {
        'essential': 'Essential',
        'standard': 'Standard',
        'high': 'High',
    }
    growth_map = {
        'no': 'No',
        'maybe': 'Maybe',
        'yes': 'Yes',
    }
    layout_map = {
        'no_preference': 'No preference',
        'single_storey': 'Single-storey',
        'two_storey': 'Two-storey',
    }

    land_size = _parse_float(form.get('land_size', '') or '')
    if land_size:
        land_value = f"{_format_number(land_size)} {unit_label}"
    else:
        land_value = 'Not provided'

    return [
        {'label': 'Occupants', 'value': form.get('occupants', '')},
        {'label': 'Household type', 'value': household_map.get(form.get('household_type'), '—')},
        {'label': 'Comfort level', 'value': comfort_map.get(form.get('comfort_level'), '—')},
        {'label': 'Future growth', 'value': growth_map.get(form.get('future_growth'), '—')},
        {'label': 'Extra rooms', 'value': extra_rooms_text},
        {'label': 'Preferred layout', 'value': layout_map.get(form.get('layout'), '—')},
        {'label': 'Land size', 'value': land_value},
        {'label': 'Unit preference', 'value': unit_label},
    ]


def _build_next_steps(summary: dict[str, float | int | str | None], *, unit_label: str, factor: float):
    bedrooms = int(summary.get('bedrooms', 0) or 0)
    gross_area = summary.get('gross_area')
    gross_text = _format_area(gross_area, factor=factor, unit_label=unit_label)
    return [
        f"Compare plans around {bedrooms} bedrooms and about {gross_text} gross area.",
        'Validate key rooms with the Space Planner tools before final design work.',
        'Use your program as input for a cost or material estimate to align budget expectations.',
    ]


def _build_pdf_url(*, form: dict, unit: str) -> Optional[str]:
    try:
        params = {
            'occupants': form.get('occupants', ''),
            'household_type': form.get('household_type', ''),
            'comfort_level': form.get('comfort_level', ''),
            'future_growth': form.get('future_growth', ''),
            'layout': form.get('layout', ''),
            'land_size': form.get('land_size', ''),
            'unit': unit,
            'extra_rooms': form.get('extra_rooms', []),
        }
        return url_for('area_calculator.pdf', **params)
    except Exception:
        return None


def _fallback_area_pdf_bytes() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, height - 2.5 * cm, "Home Space Decision Assistant")

    pdf.setFont("Helvetica", 11)
    pdf.drawString(2 * cm, height - 3.5 * cm, "PDF generation is unavailable in this environment.")
    pdf.drawString(2 * cm, height - 4.2 * cm, "Please enable HTML-to-PDF rendering for full reports.")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()


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


def _recommended_articles(*, tool_key: str):
    try:
        posts = (
            BlogPost.query
            .filter_by(status=BlogPost.STATUS_PUBLISHED)
            .order_by(BlogPost.created_at.desc())
            .limit(12)
            .all()
        )
    except Exception:
        return []

    related = []
    for post in posts:
        try:
            extras = normalize_article_extras(load_article_extras(slug=post.slug, post_id=post.id))
        except Exception:
            extras = {}
        tool_links = (extras or {}).get('tool_links') or []
        match = next((item for item in tool_links if item.get('tool_key') == tool_key), None)
        if match:
            related.append({
                'post': post,
                'title': match.get('title') or post.title,
                'body': match.get('body') or post.meta_description or '',
            })
        if len(related) >= 4:
            break

    if related:
        return related

    try:
        return [
            {
                'post': post,
                'title': post.title,
                'body': post.meta_description or '',
            }
            for post in (
                BlogPost.query
                .filter_by(status=BlogPost.STATUS_PUBLISHED)
                .order_by(BlogPost.created_at.desc())
                .limit(4)
                .all()
            )
        ]
    except Exception:
        return []


def _article_context(article_slug: Optional[str], *, tool_key: str):
    if not article_slug:
        return None
    try:
        post = BlogPost.query.filter_by(slug=article_slug, status=BlogPost.STATUS_PUBLISHED).first()
    except Exception:
        post = None
    if not post:
        return None

    try:
        extras = normalize_article_extras(load_article_extras(slug=post.slug, post_id=post.id))
    except Exception:
        extras = {}

    tool_links = (extras or {}).get('tool_links') or []
    match = next((item for item in tool_links if item.get('tool_key') == tool_key), None)
    tool = resolve_tool_link(tool_key)
    if not tool:
        return None

    return {
        'post': post,
        'title': match.get('title') if match else None,
        'body': match.get('body') if match else None,
        'cta': match.get('cta_label') if match else None,
        'tool': tool,
    }
