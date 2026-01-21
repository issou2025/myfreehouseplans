from __future__ import annotations

from io import BytesIO


def build_reality_report_pdf(*, output, html: str) -> bytes:
    """Generate a PDF report.

    Preference: WeasyPrint (HTML -> PDF) for modern document design.
    Fallback: ReportLab for maximum portability.

    This must never output prices.
    """

    # Try WeasyPrint first.
    try:
        from weasyprint import HTML

        return HTML(string=html).write_pdf()
    except Exception:
        return _build_reportlab_pdf(output=output)


def _build_reportlab_pdf(*, output) -> bytes:
    # Lightweight, dependency-only fallback.
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor

    result = output.result

    zone = result.zone
    zone_label = {
        'danger': 'RED ZONE — High risk',
        'tension': 'ORANGE ZONE — Fragile',
        'safety': 'GREEN ZONE — Stable',
    }.get(zone, 'RISK ZONE')

    zone_color = {
        'danger': HexColor('#d92d20'),
        'tension': HexColor('#f79009'),
        'safety': HexColor('#0c8f63'),
    }.get(zone, HexColor('#1f4ce4'))

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    margin_x = 18 * mm
    y = height - 22 * mm

    c.setTitle('Construction Reality Report')

    # Header
    c.setFillColor(HexColor('#0b1220'))
    c.setFont('Helvetica-Bold', 18)
    c.drawString(margin_x, y, 'Construction Reality Check')

    y -= 10 * mm
    c.setFont('Helvetica', 11)
    c.setFillColor(HexColor('#334155'))
    c.drawString(margin_x, y, 'A reality check before you start — decision, not numbers.')

    # Zone banner
    y -= 14 * mm
    c.setFillColor(zone_color)
    c.roundRect(margin_x, y - 10 * mm, width - 2 * margin_x, 12 * mm, 6 * mm, stroke=0, fill=1)
    c.setFillColor(HexColor('#ffffff'))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(margin_x + 8 * mm, y - 6.5 * mm, zone_label)

    # Summary box
    y -= 22 * mm
    c.setFillColor(HexColor('#0b1220'))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(margin_x, y, 'Project summary')

    y -= 8 * mm
    c.setFont('Helvetica', 11)
    c.setFillColor(HexColor('#111827'))
    c.drawString(margin_x, y, f"Surface: {result.surface.surface_m2} m²")

    y -= 6 * mm
    c.drawString(margin_x, y, f"Levels: {result.elevation.levels_label}")

    y -= 6 * mm
    c.drawString(margin_x, y, f"Country (auto-detected): {result.country.country_name}")

    y -= 6 * mm
    c.setFillColor(HexColor('#334155'))
    c.drawString(margin_x, y, f"Generated: {result.created_utc}")

    # Explanation
    y -= 14 * mm
    c.setFillColor(HexColor('#0b1220'))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(margin_x, y, 'What this means')

    y -= 8 * mm
    c.setFont('Helvetica', 11)
    c.setFillColor(HexColor('#111827'))
    _draw_paragraph(
        c,
        margin_x,
        y,
        width - 2 * margin_x,
        output.human.summary,
        leading=14,
        max_lines=6,
    )

    # Advice
    y -= 40 * mm
    c.setFillColor(HexColor('#0b1220'))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(margin_x, y, 'Practical advice')

    y -= 8 * mm
    c.setFont('Helvetica', 11)
    c.setFillColor(HexColor('#111827'))

    for item in output.human.advice[:4]:
        y -= 6.5 * mm
        c.drawString(margin_x, y, f"• {item}")

    # Disclaimer
    y -= 16 * mm
    c.setFillColor(HexColor('#334155'))
    c.setFont('Helvetica', 9)
    _draw_paragraph(
        c,
        margin_x,
        y,
        width - 2 * margin_x,
        'Disclaimer: This document is not a quotation and does not replace professionals. '
        'It is a prevention tool to help avoid unfinished projects. No prices are provided.',
        leading=12,
        max_lines=5,
    )

    c.showPage()
    c.save()

    return buf.getvalue()


def _draw_paragraph(c, x: float, y: float, w: float, text: str, *, leading: int, max_lines: int) -> None:
    # Minimal, predictable word-wrap for the fallback PDF.
    words = (text or '').split()
    if not words:
        return

    line = ''
    lines = []
    for word in words:
        candidate = (line + ' ' + word).strip()
        if c.stringWidth(candidate, c._fontname, c._fontsize) <= w:
            line = candidate
        else:
            lines.append(line)
            line = word
            if len(lines) >= max_lines:
                break

    if len(lines) < max_lines and line:
        lines.append(line)

    cursor = y
    for ln in lines:
        c.drawString(x, cursor, ln)
        cursor -= leading
