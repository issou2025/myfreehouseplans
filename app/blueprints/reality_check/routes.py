from __future__ import annotations

from flask import abort, flash, make_response, redirect, render_template, request, url_for

from app.core.decision_engine import run_reality_check
from app.services.reality_check_pdf import build_reality_report_pdf
from app.utils.geoip import get_country_for_ip, resolve_client_ip

from . import reality_check_bp


def _detect_country_name() -> str:
    try:
        ip = resolve_client_ip(dict(request.headers), request.remote_addr)
        return get_country_for_ip(ip)
    except Exception:
        return 'Global'


def _meta(title: str, description: str) -> dict:
    # Keep consistent with existing templates that expect meta dict.
    return {
        'title': title,
        'description': description,
        'keywords': 'construction, reality check, finish, risk, planning',
        'og_title': title,
        'og_description': description,
        'og_type': 'website',
        'canonical_url': request.url,
        'og_url': request.url,
    }


@reality_check_bp.route('/', methods=['GET'])
def landing():
    return render_template(
        'reality_check/landing.html',
        meta=_meta(
            'Construction Reality Check — Can you really finish your build?',
            'A reality check before you start. No prices. No jargon. Just a decision-focused risk zone.',
        ),
    )


@reality_check_bp.route('/start', methods=['GET', 'POST'])
def start():
    if request.method == 'GET':
        return render_template(
            'reality_check/input.html',
            meta=_meta(
                'Start your reality check — 2 simple inputs',
                'Enter only total surface and number of levels. We return a clear risk zone and practical advice.',
            ),
            values={'surface': '', 'levels': '1'},
        )

    surface = (request.form.get('surface') or '').strip()
    levels = (request.form.get('levels') or '').strip()

    # Validate early to show friendly errors.
    try:
        surface_int = int(surface)
    except Exception:
        flash('Please enter a valid whole number for surface (m²).', 'error')
        return render_template(
            'reality_check/input.html',
            meta=_meta('Start your reality check — 2 simple inputs', 'Enter only total surface and number of levels.'),
            values={'surface': surface, 'levels': levels or '1'},
        )

    try:
        # This also validates ranges and allowed choices.
        output = run_reality_check(surface_m2=surface_int, levels_choice=levels, country_name=_detect_country_name())
    except ValueError as exc:
        flash(str(exc), 'error')
        return render_template(
            'reality_check/input.html',
            meta=_meta('Start your reality check — 2 simple inputs', 'Enter only total surface and number of levels.'),
            values={'surface': surface, 'levels': levels or '1'},
        )

    return redirect(url_for('reality_check.result', s=output.result.surface.surface_m2, l=levels))


@reality_check_bp.route('/result', methods=['GET'])
def result():
    s = request.args.get('s', type=int)
    l = (request.args.get('l') or '').strip()
    if not s or not l:
        return redirect(url_for('reality_check.start'))

    try:
        output = run_reality_check(surface_m2=int(s), levels_choice=l, country_name=_detect_country_name())
    except ValueError:
        return redirect(url_for('reality_check.start'))

    return render_template(
        'reality_check/result.html',
        meta=_meta(
            'Your reality check result — Risk zone and advice',
            'A clear decision zone (green / orange / red) with realistic, non-judgmental guidance.',
        ),
        output=output,
        surface_m2=output.result.surface.surface_m2,
        levels_choice=l,
    )


@reality_check_bp.route('/report.pdf', methods=['GET'])
def report_pdf():
    s = request.args.get('s', type=int)
    l = (request.args.get('l') or '').strip()
    if not s or not l:
        abort(400)

    output = run_reality_check(surface_m2=int(s), levels_choice=l, country_name=_detect_country_name())

    html = render_template('reality_check/pdf.html', output=output)
    pdf_bytes = build_reality_report_pdf(output=output, html=html)

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename="construction-reality-report.pdf"'
    return response


@reality_check_bp.route('/how-it-works', methods=['GET'])
def how_it_works():
    return render_template(
        'reality_check/how_it_works.html',
        meta=_meta(
            'How it works — Construction Reality Check',
            'A transparent explanation: this tool is not a quotation. It is a prevention system against unfinished projects.',
        ),
    )


@reality_check_bp.route('/limitations', methods=['GET'])
def limitations():
    return render_template(
        'reality_check/limitations.html',
        meta=_meta(
            'Limitations — Construction Reality Check',
            'Honest boundaries and disclaimers. No promises. No prices. A reality-oriented decision aid.',
        ),
    )
