from __future__ import annotations

from io import BytesIO


def build_progress_report_pdf(*, html: str, result) -> bytes:
    """Generate a detailed PDF report.

    Institutional preference:
      - ReportLab + Matplotlib (charts + progress bars)

    Optional fallback:
      - WeasyPrint (HTML -> PDF) if ReportLab/Matplotlib isn't available.
    """

    try:
        return _reportlab_with_charts(result=result)
    except Exception:
        try:
            from weasyprint import HTML

            return HTML(string=html).write_pdf()
        except Exception:
            # As a last resort, return a minimal ReportLab PDF.
            return _reportlab_minimal(result=result)


def _reportlab_with_charts(*, result) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader

    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    left = 18 * mm
    right = 18 * mm
    top = 18 * mm
    bottom = 18 * mm
    y = h - top

    def heading(text: str):
        nonlocal y
        c.setFillColor(HexColor('#0b1220'))
        c.setFont('Helvetica-Bold', 16)
        c.drawString(left, y, text)
        y -= 9 * mm

    def subheading(text: str):
        nonlocal y
        c.setFillColor(HexColor('#0b1220'))
        c.setFont('Helvetica-Bold', 12)
        c.drawString(left, y, text)
        y -= 7 * mm

    def paragraph(text: str, *, color: str = '#334155', size: int = 10):
        nonlocal y
        c.setFillColor(HexColor(color))
        c.setFont('Helvetica', size)
        # Very small wrapping implementation
        max_width = (w - left - right)
        words = str(text).split(' ')
        line = ''
        for word in words:
            cand = (line + ' ' + word).strip()
            if c.stringWidth(cand, 'Helvetica', size) > max_width and line:
                c.drawString(left, y, line)
                y -= 5.2 * mm
                line = word
            else:
                line = cand
        if line:
            c.drawString(left, y, line)
            y -= 5.2 * mm

    def ensure_space(mm_needed: float):
        nonlocal y
        if y - (mm_needed * mm) < bottom:
            c.showPage()
            y = h - top

    def draw_progress_bar(label: str, ratio: float, *, color: str):
        nonlocal y
        ensure_space(16)
        c.setFillColor(HexColor('#0b1220'))
        c.setFont('Helvetica-Bold', 10)
        c.drawString(left, y, label)
        y -= 4.8 * mm

        bar_w = w - left - right
        bar_h = 6 * mm
        c.setFillColor(HexColor('#eef2ff'))
        c.roundRect(left, y - bar_h, bar_w, bar_h, 3 * mm, fill=1, stroke=0)

        filled = max(0.0, min(1.0, float(ratio)))
        c.setFillColor(HexColor(color))
        c.roundRect(left, y - bar_h, bar_w * filled, bar_h, 3 * mm, fill=1, stroke=0)
        y -= 8.5 * mm

    def fig_to_png_bytes(fig) -> bytes:
        out = BytesIO()
        fig.savefig(out, format='png', dpi=170, bbox_inches='tight')
        plt.close(fig)
        return out.getvalue()

    c.setTitle('Construction Reality Report')

    # Title page
    heading('Construction Reality Report')
    paragraph('Realistic projection based on global standards (no quotation, no unit prices).', size=11)
    paragraph('This report helps prevent unfinished projects by showing where similar projects tend to stall under economic reality.', size=10)

    ensure_space(18)
    subheading('Project summary')
    inp = result.inputs
    currency = getattr(inp, 'currency', 'EUR')
    paragraph(f"Building type: {inp.building_type}", color='#111827', size=10)
    paragraph(f"Floors: {inp.floors}", color='#111827', size=10)
    paragraph(f"Structural material: {inp.material}", color='#111827', size=10)
    paragraph(f"Surface area: {float(inp.area_value):.0f} {inp.area_unit}", color='#111827', size=10)
    paragraph(f"Currency: {currency}", color='#111827', size=10)
    if inp.total_budget is not None:
        paragraph(f"Total available now (your input): {float(inp.total_budget):.0f} {currency}", color='#111827', size=10)
    if inp.monthly_contribution is not None:
        paragraph(f"Monthly contribution (your input): {float(inp.monthly_contribution):.0f} {currency}", color='#111827', size=10)
    paragraph(f"Country (auto-detected): {inp.country_name}", color='#334155', size=9)

    ensure_space(14)
    subheading('Core decision')
    paragraph(f"Stopping point tends to appear around: {result.stopping_phase}", color='#111827', size=11)
    paragraph('We use internal international reference standards only as a guardrail. We never display unit prices or phase prices.', size=10)

    ensure_space(22)
    subheading('Phase progression')
    colors = {
        'green': '#0c8f63',
        'orange': '#f79009',
        'red': '#d92d20',
    }
    for st in result.statuses:
        draw_progress_bar(f"{st.phase} — {st.status.upper()}", 1.0 if st.status == 'green' else (0.55 if st.status == 'orange' else 0.15), color=colors.get(st.status, '#64748b'))

    ensure_space(18)
    subheading('Economic reality check')
    paragraph('Construction follows global economic constraints. If coverage is too low, projects typically stop early — even with strong motivation.', size=10)
    paragraph('The tool speaks in probabilities and prevention: it shows where risk concentrates so you can simplify early.', size=10)

    # Charts page
    c.showPage()
    y = h - top
    heading('Charts')

    # Pie chart: reachable vs unreachable
    ensure_space(90)
    subheading('Reachable vs unreachable portion (indicative)')
    reachable = max(0.0, min(1.0, float(getattr(result, 'reachable_ratio', 0.0))))
    unreachable = max(0.0, 1.0 - reachable)
    fig1 = plt.figure(figsize=(4.8, 3.3))
    ax1 = fig1.add_subplot(111)
    ax1.pie([reachable, unreachable], labels=['Reachable', 'Unreachable'], colors=['#0c8f63', '#d92d20'], autopct='%1.0f%%', startangle=90)
    ax1.axis('equal')
    img1 = ImageReader(BytesIO(fig_to_png_bytes(fig1)))
    c.drawImage(img1, left, y - 75 * mm, width=170 * mm, height=70 * mm, preserveAspectRatio=True, mask='auto')
    y -= 82 * mm

    # Line chart: progress over time
    ensure_space(100)
    subheading('Progress over time (if monthly contribution)')
    months = list(getattr(result, 'progress_months', []) or [])
    ratios = list(getattr(result, 'progress_ratios', []) or [])
    if len(months) >= 2 and len(months) == len(ratios):
        fig2 = plt.figure(figsize=(5.4, 3.2))
        ax2 = fig2.add_subplot(111)
        ax2.plot(months, ratios, color='#1f4ce4', linewidth=2)
        ax2.set_ylim(0, 1.25)
        ax2.set_xlabel('Months')
        ax2.set_ylabel('Coverage ratio')
        ax2.grid(True, alpha=0.25)
        img2 = ImageReader(BytesIO(fig_to_png_bytes(fig2)))
        c.drawImage(img2, left, y - 75 * mm, width=170 * mm, height=70 * mm, preserveAspectRatio=True, mask='auto')
        y -= 82 * mm
    else:
        paragraph('No monthly contribution was provided, so time-based progress is not simulated.', size=10)

    # Explanation + scenarios
    ensure_space(40)
    subheading('Why projects stop here')
    paragraph('When coverage is low, early phases consume the available capacity before the project becomes livable. Late phases are fragile and often require continuity.', size=10)

    ensure_space(30)
    subheading('Improvement scenarios (directional)')
    for s in (result.scenarios or [])[:6]:
        paragraph(f"• {s.get('title')}: {s.get('effect')}", color='#111827', size=10)

    ensure_space(26)
    subheading('Disclaimer')
    paragraph('This report is an indicative simulation. It is not a quotation, not a cost estimate, and not a substitute for professional studies.', size=9)

    c.save()
    return buf.getvalue()


def _reportlab_minimal(*, result) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    x = 18 * mm
    y = h - 20 * mm

    c.setTitle('Construction Reality Report')
    c.setFillColor(HexColor('#0b1220'))
    c.setFont('Helvetica-Bold', 18)
    c.drawString(x, y, 'Construction Reality Report')

    y -= 10 * mm
    c.setFillColor(HexColor('#334155'))
    c.setFont('Helvetica', 10)
    c.drawString(x, y, 'Indicative simulation based on global standards. No unit prices shown.')

    y -= 14 * mm
    c.setFillColor(HexColor('#0b1220'))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(x, y, f"Stopping point: {result.stopping_phase}")

    y -= 10 * mm
    c.setFillColor(HexColor('#111827'))
    c.setFont('Helvetica', 10)
    for st in result.statuses:
        if y < 25 * mm:
            c.showPage()
            y = h - 20 * mm
        c.drawString(x, y, f"• {st.phase}: {st.status.upper()} — {st.note}")
        y -= 6 * mm

    c.showPage()
    c.save()
    return buf.getvalue()
