from __future__ import annotations

from io import BytesIO


def build_progress_report_pdf(*, html: str, result) -> bytes:
    """Generate a detailed PDF report.

    Preference: WeasyPrint (HTML -> PDF) for clean typography.
    Fallback: ReportLab for portability.
    """

    try:
        from weasyprint import HTML

        return HTML(string=html).write_pdf()
    except Exception:
        return _reportlab_fallback(result=result)


def _reportlab_fallback(*, result) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    x = 18 * mm
    y = h - 20 * mm

    c.setTitle('Construction Progress Reality Report')

    c.setFillColor(HexColor('#0b1220'))
    c.setFont('Helvetica-Bold', 18)
    c.drawString(x, y, 'Construction Progress Reality Report')

    y -= 8 * mm
    c.setFillColor(HexColor('#334155'))
    c.setFont('Helvetica', 11)
    c.drawString(x, y, 'A realistic projection of how far a project tends to progress.')

    y -= 14 * mm
    c.setFillColor(HexColor('#0b1220'))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(x, y, 'Project summary')

    y -= 8 * mm
    c.setFillColor(HexColor('#111827'))
    c.setFont('Helvetica', 11)

    inp = result.inputs
    c.drawString(x, y, f"Building type: {inp.building_type}")
    y -= 6 * mm
    c.drawString(x, y, f"Floors: {inp.floors}")
    y -= 6 * mm
    c.drawString(x, y, f"Material: {inp.material}")
    y -= 6 * mm
    c.drawString(x, y, f"Area: {inp.area_value:.0f} {inp.area_unit}")
    y -= 6 * mm
    c.setFillColor(HexColor('#334155'))
    c.drawString(x, y, f"Country (auto-detected): {inp.country_name}")

    y -= 12 * mm
    c.setFillColor(HexColor('#0b1220'))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(x, y, 'Stopping point')

    y -= 8 * mm
    c.setFillColor(HexColor('#111827'))
    c.setFont('Helvetica', 11)
    c.drawString(x, y, f"Tends to stop around: {result.stopping_phase}")

    y -= 12 * mm
    c.setFillColor(HexColor('#0b1220'))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(x, y, 'Phase progression')

    y -= 8 * mm
    c.setFillColor(HexColor('#111827'))
    c.setFont('Helvetica', 10)
    for st in result.statuses:
        if y < 25 * mm:
            c.showPage()
            y = h - 20 * mm
        c.drawString(x, y, f"• {st.phase}: {st.status.upper()} — {st.note}")
        y -= 5.5 * mm

    if y < 35 * mm:
        c.showPage()
        y = h - 20 * mm

    y -= 6 * mm
    c.setFillColor(HexColor('#0b1220'))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(x, y, 'Advice')

    y -= 8 * mm
    c.setFillColor(HexColor('#111827'))
    c.setFont('Helvetica', 10)
    for item in result.advice[:6]:
        if y < 25 * mm:
            c.showPage()
            y = h - 20 * mm
        c.drawString(x, y, f"• {item}")
        y -= 5.5 * mm

    y -= 10 * mm
    c.setFillColor(HexColor('#334155'))
    c.setFont('Helvetica', 9)
    c.drawString(x, y, 'Disclaimer: This is an indicative simulation. Not a quotation, not a cost estimate, not a substitute for professional studies.')

    c.showPage()
    c.save()
    return buf.getvalue()
