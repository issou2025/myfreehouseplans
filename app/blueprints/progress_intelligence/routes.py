from __future__ import annotations

from flask import abort, current_app, flash, make_response, redirect, render_template, request, url_for

from app.services.progress_intelligence.engine import Inputs, simulate
from app.services.progress_intelligence.pdf import build_progress_report_pdf
from app.services.progress_intelligence.token import dumps_payload, loads_payload
from app.utils.geoip import get_country_for_ip, resolve_client_ip

from . import progress_intelligence_bp


def _detect_country_name() -> str:
    try:
        ip = resolve_client_ip(dict(request.headers), request.remote_addr)
        return get_country_for_ip(ip)
    except Exception:
        return 'Global'


def _meta(title: str, description: str) -> dict:
    return {
        'title': title,
        'description': description,
        'keywords': 'construction, progress, reality report, simulation, prevention',
        'og_title': title,
        'og_description': description,
        'og_type': 'website',
        'canonical_url': request.url,
        'og_url': request.url,
    }


def _lang() -> str:
    lang = (request.args.get('lang') or request.form.get('lang') or 'en').strip().lower()
    return 'fr' if lang.startswith('fr') else 'en'


def _labels(lang: str) -> dict:
    # Minimal bilingual readiness (expand later).
    if lang == 'fr':
        return {
            'tool_name': 'Intelligence de Progression de Construction',
            'cta_start': 'Démarrer',
        }
    return {
        'tool_name': 'Construction Progress Intelligence',
        'cta_start': 'Start',
    }


@progress_intelligence_bp.route('/', methods=['GET'])
def landing():
    lang = _lang()
    labels = _labels(lang)
    return render_template(
        'progress_intelligence/landing.html',
        meta=_meta(
            'Construction Progress Intelligence — Where will it realistically stop?',
            'A global, non-technical simulation that shows where projects tend to stop — without quotes or construction jargon.',
        ),
        lang=lang,
        labels=labels,
    )


@progress_intelligence_bp.route('/start', methods=['GET', 'POST'])
def start():
    lang = _lang()
    labels = _labels(lang)

    if request.method == 'GET':
        return render_template(
            'progress_intelligence/input.html',
            meta=_meta('Start — Progress Intelligence', 'Enter a few simple inputs. No registration. No jargon.'),
            lang=lang,
            labels=labels,
            values={},
        )

    # Collect inputs
    building_type = (request.form.get('building_type') or '').strip()
    floors = (request.form.get('number_of_floors') or '').strip()
    material = (request.form.get('structural_material') or '').strip()

    area_value = (request.form.get('surface_area') or '').strip()
    area_unit = (request.form.get('surface_unit') or 'm2').strip()

    total_budget = (request.form.get('total_budget') or '').strip()
    monthly = (request.form.get('monthly_contribution') or '').strip()
    max_monthly_effort = bool(request.form.get('max_monthly_effort'))

    # Basic validation
    try:
        area_value_f = float(area_value)
    except Exception:
        flash('Please enter a valid surface area number.', 'error')
        return render_template(
            'progress_intelligence/input.html',
            meta=_meta('Start — Progress Intelligence', 'Enter a few simple inputs. No registration. No jargon.'),
            lang=lang,
            labels=labels,
            values=request.form,
        )

    def safe_float(v: str) -> float | None:
        if not v:
            return None
        try:
            out = float(v)
        except Exception:
            return None
        return 0.0 if out < 0 else out

    payload = {
        'building_type': building_type,
        'floors': floors,
        'material': material,
        'area_value': area_value_f,
        'area_unit': area_unit,
        'total_budget': safe_float(total_budget),
        'monthly_contribution': safe_float(monthly),
        'max_monthly_effort': bool(max_monthly_effort),
        'lang': lang,
    }

    token = dumps_payload(current_app.config.get('SECRET_KEY', 'dev'), payload)
    return redirect(url_for('progress_intelligence.result', t=token, lang=lang))


@progress_intelligence_bp.route('/result', methods=['GET'])
def result():
    lang = _lang()
    labels = _labels(lang)

    token = request.args.get('t')
    if not token:
        return redirect(url_for('progress_intelligence.start', lang=lang))

    payload = loads_payload(current_app.config.get('SECRET_KEY', 'dev'), token)
    if not payload:
        flash('Your session link is invalid or expired. Please try again.', 'warning')
        return redirect(url_for('progress_intelligence.start', lang=lang))

    inputs = Inputs(
        building_type=str(payload.get('building_type') or ''),
        floors=str(payload.get('floors') or ''),
        material=str(payload.get('material') or ''),
        area_value=float(payload.get('area_value') or 0.0),
        area_unit=str(payload.get('area_unit') or 'm2'),
        total_budget=payload.get('total_budget', None),
        monthly_contribution=payload.get('monthly_contribution', None),
        max_monthly_effort=bool(payload.get('max_monthly_effort', False)),
        country_name=_detect_country_name(),
        lang=lang,
    )

    try:
        res = simulate(inputs)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('progress_intelligence.start', lang=lang))

    return render_template(
        'progress_intelligence/result.html',
        meta=_meta('Result — Progress Intelligence', 'Visual phase progression and a clear stopping point.'),
        lang=lang,
        labels=labels,
        token=token,
        result=res,
    )


@progress_intelligence_bp.route('/report.pdf', methods=['GET'])
def report_pdf():
    lang = _lang()
    token = request.args.get('t')
    if not token:
        abort(400)

    payload = loads_payload(current_app.config.get('SECRET_KEY', 'dev'), token)
    if not payload:
        abort(400)

    inputs = Inputs(
        building_type=str(payload.get('building_type') or ''),
        floors=str(payload.get('floors') or ''),
        material=str(payload.get('material') or ''),
        area_value=float(payload.get('area_value') or 0.0),
        area_unit=str(payload.get('area_unit') or 'm2'),
        total_budget=payload.get('total_budget', None),
        monthly_contribution=payload.get('monthly_contribution', None),
        max_monthly_effort=bool(payload.get('max_monthly_effort', False)),
        country_name=_detect_country_name(),
        lang=lang,
    )

    res = simulate(inputs)
    html = render_template('progress_intelligence/pdf.html', result=res)
    pdf_bytes = build_progress_report_pdf(html=html, result=res)

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename="construction-progress-reality-report.pdf"'
    return response


@progress_intelligence_bp.route('/how-it-works', methods=['GET'])
def how_it_works():
    lang = _lang()
    labels = _labels(lang)
    return render_template(
        'progress_intelligence/how_it_works.html',
        meta=_meta('How it works — Progress Intelligence', 'Transparent explanation of the simulation model.'),
        lang=lang,
        labels=labels,
    )


@progress_intelligence_bp.route('/limitations', methods=['GET'])
def limitations():
    lang = _lang()
    labels = _labels(lang)
    return render_template(
        'progress_intelligence/limitations.html',
        meta=_meta('Limitations — Progress Intelligence', 'Honest boundaries and disclaimers.'),
        lang=lang,
        labels=labels,
    )
