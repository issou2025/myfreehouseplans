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
    from reportlab.lib.colors import HexColor, Color
    from reportlab.lib.utils import ImageReader

    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    left = 20 * mm
    right = 20 * mm
    top = 20 * mm
    bottom = 20 * mm
    y = h - top

    def draw_header():
        """Draw professional header with branding on each page"""
        c.saveState()
        # Header background bar
        c.setFillColor(HexColor('#1e3a8a'))
        c.rect(0, h - 15 * mm, w, 15 * mm, fill=1, stroke=0)
        
        # Site branding
        c.setFillColor(HexColor('#ffffff'))
        c.setFont('Helvetica-Bold', 11)
        c.drawString(left, h - 9 * mm, 'MyFreeHousePlans.com')
        c.setFont('Helvetica', 8)
        c.drawString(left, h - 12 * mm, 'Professional Construction Intelligence Report')
        
        # Page number on the right
        c.setFont('Helvetica', 9)
        page_num = c.getPageNumber()
        c.drawRightString(w - right, h - 9.5 * mm, f'Page {page_num}')
        c.restoreState()

    def draw_watermark():
        """Subtle diagonal watermark across the page"""
        c.saveState()
        try:
            c.setFillAlpha(0.05)
        except Exception:
            pass
        c.setFillColor(Color(0.1, 0.2, 0.5, alpha=0.05))
        c.setFont('Helvetica', 28)
        c.translate(w / 2, h / 2)
        c.rotate(45)
        text = 'MyFreeHousePlans.com'
        for x in range(-500, 501, 250):
            for y_offset in range(-400, 401, 150):
                c.drawString(x, y_offset, text)
        c.restoreState()
    
    def draw_decorative_line(color='#3b82f6', height=0.8):
        """Draw a decorative accent line"""
        nonlocal y
        c.setStrokeColor(HexColor(color))
        c.setLineWidth(height * mm)
        c.line(left, y, left + 40 * mm, y)
        y -= 4 * mm

    def heading(text: str, color='#0f172a'):
        nonlocal y
        c.setFillColor(HexColor(color))
        c.setFont('Helvetica-Bold', 18)
        c.drawString(left, y, text)
        y -= 8 * mm

    def subheading(text: str, color='#1e40af'):
        nonlocal y
        draw_decorative_line(color='#3b82f6')
        c.setFillColor(HexColor(color))
        c.setFont('Helvetica-Bold', 13)
        c.drawString(left, y, text)
        y -= 7 * mm

    def info_box(label: str, value: str, icon_color='#3b82f6'):
        """Draw a colored information box"""
        nonlocal y
        ensure_space(14)
        
        # Box background
        c.setFillColor(HexColor('#f1f5f9'))
        c.roundRect(left, y - 10 * mm, (w - left - right) / 2 - 3 * mm, 10 * mm, 2 * mm, fill=1, stroke=0)
        
        # Icon circle
        c.setFillColor(HexColor(icon_color))
        c.circle(left + 4 * mm, y - 5 * mm, 2.5 * mm, fill=1, stroke=0)
        
        # Text
        c.setFillColor(HexColor('#0f172a'))
        c.setFont('Helvetica-Bold', 11)
        c.drawString(left + 8 * mm, y - 4 * mm, value)
        c.setFont('Helvetica', 8)
        c.setFillColor(HexColor('#64748b'))
        c.drawString(left + 8 * mm, y - 7.5 * mm, label)


    def paragraph(text: str, *, color: str = '#475569', size: int = 10, bold: bool = False):
        nonlocal y
        c.setFillColor(HexColor(color))
        font_name = 'Helvetica-Bold' if bold else 'Helvetica'
        c.setFont(font_name, size)
        # Improved text wrapping
        max_width = (w - left - right)
        words = str(text).split(' ')
        line = ''
        for word in words:
            cand = (line + ' ' + word).strip()
            if c.stringWidth(cand, font_name, size) > max_width and line:
                c.drawString(left, y, line)
                y -= (size * 0.42) * mm
                line = word
            else:
                line = cand
        if line:
            c.drawString(left, y, line)
            y -= (size * 0.42) * mm
        y -= 1.5 * mm  # Extra spacing after paragraph

    def ensure_space(mm_needed: float):
        nonlocal y
        if y - (mm_needed * mm) < (bottom + 20 * mm):
            new_page()

    def new_page():
        nonlocal y
        c.showPage()
        draw_header()
        draw_watermark()
        y = h - (top + 20 * mm)  # Account for header space

    def draw_progress_bar(label: str, ratio: float, *, color: str, status_text: str = ''):
        nonlocal y
        ensure_space(18)
        
        # Label with status
        c.setFillColor(HexColor('#0f172a'))
        c.setFont('Helvetica-Bold', 11)
        c.drawString(left, y, label)
        
        if status_text:
            c.setFont('Helvetica', 9)
            c.setFillColor(HexColor('#64748b'))
            c.drawString(left + 85 * mm, y, status_text)
        
        y -= 5 * mm

        # Enhanced progress bar with shadow effect
        bar_w = w - left - right
        bar_h = 7 * mm
        
        # Shadow
        c.setFillColor(HexColor('#cbd5e1'))
        c.roundRect(left + 0.5 * mm, y - bar_h - 0.5 * mm, bar_w, bar_h, 3.5 * mm, fill=1, stroke=0)
        
        # Background
        c.setFillColor(HexColor('#f1f5f9'))
        c.roundRect(left, y - bar_h, bar_w, bar_h, 3.5 * mm, fill=1, stroke=0)

        # Filled portion with gradient effect
        filled = max(0.0, min(1.0, float(ratio)))
        if filled > 0:
            c.setFillColor(HexColor(color))
            c.roundRect(left, y - bar_h, bar_w * filled, bar_h, 3.5 * mm, fill=1, stroke=0)
            
            # Highlight on top
            c.setFillColor(Color(1, 1, 1, alpha=0.2))
            c.roundRect(left, y - bar_h + bar_h * 0.5, bar_w * filled, bar_h * 0.3, 3.5 * mm, fill=1, stroke=0)
        
        y -= 10 * mm

    def fig_to_png_bytes(fig) -> bytes:
        out = BytesIO()
        fig.savefig(out, format='png', dpi=200, bbox_inches='tight', facecolor='white', edgecolor='none')
        plt.close(fig)
        return out.getvalue()

    c.setTitle('Construction Progress Intelligence Report - MyFreeHousePlans.com')
    draw_header()
    draw_watermark()
    y = h - (top + 20 * mm)  # Start below header

    # ========== COVER PAGE ==========
    # Hero title with decorative elements
    ensure_space(60)
    
    # Large colored box for title
    c.setFillColor(HexColor('#1e3a8a'))
    c.roundRect(left - 5 * mm, y - 35 * mm, w - left - right + 10 * mm, 35 * mm, 4 * mm, fill=1, stroke=0)
    
    c.setFillColor(HexColor('#ffffff'))
    c.setFont('Helvetica-Bold', 22)
    title_y = y - 12 * mm
    c.drawString(left + 2 * mm, title_y, 'Construction Progress')
    c.drawString(left + 2 * mm, title_y - 8 * mm, 'Intelligence Report')
    
    c.setFont('Helvetica', 11)
    c.drawString(left + 2 * mm, title_y - 16 * mm, 'Professional Analysis & Strategic Planning')
    
    c.setFont('Helvetica-Bold', 10)
    c.drawString(left + 2 * mm, title_y - 22 * mm, '✓ FREE Report • Generated by MyFreeHousePlans.com')
    
    y -= 40 * mm
    
    # Introductory message
    ensure_space(25)
    c.setFillColor(HexColor('#f8fafc'))
    c.roundRect(left, y - 20 * mm, w - left - right, 20 * mm, 3 * mm, fill=1, stroke=0)
    
    c.setFillColor(HexColor('#0f172a'))
    c.setFont('Helvetica-Bold', 12)
    c.drawString(left + 3 * mm, y - 5 * mm, 'About This Report')
    
    c.setFont('Helvetica', 10)
    c.setFillColor(HexColor('#475569'))
    text_y = y - 9 * mm
    c.drawString(left + 3 * mm, text_y, 'This comprehensive analysis provides realistic projections for your construction project,')
    c.drawString(left + 3 * mm, text_y - 4 * mm, 'based on international construction data and proven methodologies.')
    c.drawString(left + 3 * mm, text_y - 8 * mm, 'Generated exclusively for you by www.MyFreeHousePlans.com')
    
    y -= 25 * mm

    # ========== PROJECT SUMMARY ==========
    ensure_space(20)
    subheading('📋 Project Summary', color='#1e40af')
    
    inp = result.inputs
    currency = getattr(inp, 'currency', 'EUR')
    
    # Create a grid of info boxes
    y_saved = y
    info_items = [
        (f"{inp.building_type}", "Building Type", '#3b82f6'),
        (f"{float(inp.area_value):.0f} {inp.area_unit}", "Surface Area", '#10b981'),
        (f"{inp.floors}", "Number of Floors", '#f59e0b'),
        (f"{inp.material}", "Structural Material", '#8b5cf6'),
    ]
    
    for i, (value, label, color) in enumerate(info_items):
        if i % 2 == 0:
            y = y_saved
        else:
            y = y_saved
            
        # Draw colored card
        card_x = left if i % 2 == 0 else left + (w - left - right) / 2 + 3 * mm
        card_w = (w - left - right) / 2 - 3 * mm
        
        c.setFillColor(HexColor('#f8fafc'))
        c.roundRect(card_x, y - 12 * mm, card_w, 12 * mm, 2 * mm, fill=1, stroke=0)
        
        # Colored accent bar
        c.setFillColor(HexColor(color))
        c.roundRect(card_x, y - 12 * mm, 3 * mm, 12 * mm, 2 * mm, fill=1, stroke=0)
        
        # Value
        c.setFillColor(HexColor('#0f172a'))
        c.setFont('Helvetica-Bold', 12)
        c.drawString(card_x + 5 * mm, y - 5 * mm, value)
        
        # Label
        c.setFillColor(HexColor('#64748b'))
        c.setFont('Helvetica', 8)
        c.drawString(card_x + 5 * mm, y - 9 * mm, label)
        
        if i % 2 == 1:
            y_saved -= 14 * mm
    
    y = y_saved
    
    # Budget information
    ensure_space(15)
    if inp.total_budget is not None:
        paragraph(f"💰 Total Budget Available: {float(inp.total_budget):.0f} {currency}", color='#0f172a', size=10, bold=True)
    if inp.monthly_contribution is not None:
        paragraph(f"📅 Monthly Contribution: {float(inp.monthly_contribution):.0f} {currency}", color='#0f172a', size=10, bold=True)
    
    paragraph(f"🌍 Country Context: {inp.country_name}", color='#64748b', size=9)

    # ========== KEY FINDINGS ==========
    ensure_space(25)
    subheading('🎯 Critical Stopping Point Analysis', color='#dc2626')
    
    # Highlighted box for stopping point
    c.setFillColor(HexColor('#fef2f2'))
    c.roundRect(left, y - 18 * mm, w - left - right, 18 * mm, 3 * mm, fill=1, stroke=0)
    
    c.setStrokeColor(HexColor('#dc2626'))
    c.setLineWidth(2)
    c.roundRect(left, y - 18 * mm, w - left - right, 18 * mm, 3 * mm, fill=0, stroke=1)
    
    c.setFillColor(HexColor('#dc2626'))
    c.setFont('Helvetica-Bold', 11)
    c.drawString(left + 3 * mm, y - 5 * mm, '⚠️  PREDICTED STOPPING POINT:')
    
    c.setFont('Helvetica-Bold', 16)
    c.setFillColor(HexColor('#0f172a'))
    c.drawString(left + 3 * mm, y - 11 * mm, result.stopping_phase)
    
    c.setFont('Helvetica', 9)
    c.setFillColor(HexColor('#475569'))
    c.drawString(left + 3 * mm, y - 15 * mm, '↳ Early phases consume scarce resources; late phases demand sustained continuity')
    
    y -= 22 * mm

    ensure_space(12)
    paragraph('Construction follows universal economic constraints. This analysis uses international reference standards', size=10)
    paragraph('to identify realistic progression patterns and potential stopping points in your project.', size=10)

    # ========== PHASE PROGRESSION ==========
    ensure_space(22)
    subheading('📊 Construction Phase Progression', color='#1e40af')
    
    colors = {
        'green': '#10b981',
        'orange': '#f59e0b',
        'red': '#ef4444',
    }
    
    status_labels = {
        'green': '✓ Fully Reached',
        'orange': '⚠ Fragile/Partial',
        'red': '✗ Not Reached',
    }
    
    for st in result.statuses:
        ratio = 1.0 if st.status == 'green' else (0.6 if st.status == 'orange' else 0.2)
        draw_progress_bar(
            f"{st.phase}", 
            ratio, 
            color=colors.get(st.status, '#64748b'),
            status_text=status_labels.get(st.status, '')
        )

    # ========== INTELLIGENCE EXPLANATION ==========
    ensure_space(20)
    subheading('🧠 How The Analysis Works', color='#7c3aed')
    
    paragraph('Our intelligent system analyzes multiple factors to predict realistic project progression:', size=10, bold=True)
    y -= 2 * mm
    
    bullet_points = [
        ('📐', 'Surface Scale', 'Sets baseline complexity and establishes continuity requirements'),
        ('🏢', 'Floor Count', 'Multiplies risk in later phases regardless of surface area'),
        ('🧱', 'Material Choice', 'Determines where maximum effort concentrates (early vs late phases)'),
        ('💵', 'Budget Rhythm', 'Monthly continuity decides whether work maintains momentum'),
    ]
    
    for icon, title, desc in bullet_points:
        ensure_space(10)
        c.setFillColor(HexColor('#ede9fe'))
        c.roundRect(left, y - 8 * mm, w - left - right, 8 * mm, 2 * mm, fill=1, stroke=0)
        
        c.setFillColor(HexColor('#7c3aed'))
        c.setFont('Helvetica-Bold', 11)
        c.drawString(left + 2 * mm, y - 4 * mm, f"{icon} {title}")
        
        c.setFillColor(HexColor('#475569'))
        c.setFont('Helvetica', 9)
        c.drawString(left + 2 * mm, y - 7 * mm, f"  → {desc}")
        
        y -= 10 * mm

    # ========== CHARTS PAGE ==========
    new_page()
    heading('📈 Visual Analytics & Data Insights', color='#0f172a')

    # Pie chart: reachable vs unreachable with enhanced styling
    ensure_space(95)
    subheading('Project Reachability Analysis', color='#059669')
    
    reachable = max(0.0, min(1.0, float(getattr(result, 'reachable_ratio', 0.0))))
    unreachable = max(0.0, 1.0 - reachable)
    
    fig1 = plt.figure(figsize=(5.5, 4), facecolor='white')
    ax1 = fig1.add_subplot(111)
    
    colors_pie = ['#10b981', '#ef4444']
    explode = (0.05, 0.05)
    wedges, texts, autotexts = ax1.pie(
        [reachable, unreachable], 
        labels=['Reachable Portion', 'Unreachable Portion'], 
        colors=colors_pie, 
        autopct='%1.1f%%', 
        startangle=90,
        explode=explode,
        shadow=True,
        textprops={'fontsize': 11, 'weight': 'bold'}
    )
    
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(12)
        autotext.set_weight('bold')
    
    ax1.axis('equal')
    ax1.set_title('Reachable vs Unreachable Construction Phases', fontsize=13, weight='bold', pad=15)
    
    img1 = ImageReader(BytesIO(fig_to_png_bytes(fig1)))
    c.drawImage(img1, left, y - 80 * mm, width=170 * mm, height=75 * mm, preserveAspectRatio=True, mask='auto')
    y -= 85 * mm

    # Line chart: progress over time with enhanced styling
    ensure_space(105)
    subheading('Timeline Projection (Monthly Progress)', color='#2563eb')
    
    months = list(getattr(result, 'progress_months', []) or [])
    ratios = list(getattr(result, 'progress_ratios', []) or [])
    
    if len(months) >= 2 and len(months) == len(ratios):
        fig2 = plt.figure(figsize=(6, 3.8), facecolor='white')
        ax2 = fig2.add_subplot(111)
        
        # Plot line with markers
        ax2.plot(months, ratios, color='#2563eb', linewidth=2.5, marker='o', markersize=6, 
                 markerfacecolor='#3b82f6', markeredgecolor='white', markeredgewidth=1.5)
        
        # Fill area under the curve
        ax2.fill_between(months, ratios, alpha=0.2, color='#3b82f6')
        
        ax2.set_ylim(0, 1.3)
        ax2.set_xlabel('Months of Continuous Work', fontsize=11, weight='bold')
        ax2.set_ylabel('Project Completion Ratio', fontsize=11, weight='bold')
        ax2.set_title('Predicted Progress Over Time', fontsize=13, weight='bold', pad=12)
        ax2.grid(True, alpha=0.3, linestyle='--', linewidth=0.7)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        
        img2 = ImageReader(BytesIO(fig_to_png_bytes(fig2)))
        c.drawImage(img2, left, y - 80 * mm, width=170 * mm, height=75 * mm, preserveAspectRatio=True, mask='auto')
        y -= 85 * mm
    else:
        c.setFillColor(HexColor('#fef3c7'))
        c.roundRect(left, y - 15 * mm, w - left - right, 15 * mm, 2 * mm, fill=1, stroke=0)
        
        c.setFillColor(HexColor('#92400e'))
        c.setFont('Helvetica', 10)
        c.drawString(left + 3 * mm, y - 8 * mm, 'ℹ️  No monthly contribution data was provided for time-based projection.')
        y -= 18 * mm

    # ========== WHY PROJECTS STOP ==========
    ensure_space(35)
    subheading('⚠️ Common Failure Patterns', color='#dc2626')
    
    c.setFillColor(HexColor('#fef2f2'))
    c.roundRect(left, y - 25 * mm, w - left - right, 25 * mm, 3 * mm, fill=1, stroke=0)
    
    c.setFillColor(HexColor('#0f172a'))
    c.setFont('Helvetica-Bold', 11)
    c.drawString(left + 3 * mm, y - 5 * mm, 'Why Construction Projects Typically Stop at This Phase:')
    
    c.setFont('Helvetica', 10)
    c.setFillColor(HexColor('#475569'))
    text_y = y - 10 * mm
    
    reasons = [
        '• When coverage is low, early phases consume available capacity before livability',
        '• Late phases require sustained continuity that is often disrupted',
        '• Resource depletion accelerates as complexity compounds over time',
        '• Financial and logistical challenges multiply in finishing stages'
    ]
    
    for reason in reasons:
        c.drawString(left + 3 * mm, text_y, reason)
        text_y -= 4.5 * mm
    
    y -= 28 * mm

    # ========== IMPROVEMENT SCENARIOS ==========
    ensure_space(30)
    subheading('💡 Strategic Improvement Options', color='#059669')
    
    paragraph('Consider these evidence-based strategies to improve project outcomes:', size=10, bold=True)
    y -= 2 * mm
    
    for i, s in enumerate((result.scenarios or [])[:6], 1):
        ensure_space(10)
        
        c.setFillColor(HexColor('#ecfdf5'))
        c.roundRect(left, y - 9 * mm, w - left - right, 9 * mm, 2 * mm, fill=1, stroke=0)
        
        c.setFillColor(HexColor('#059669'))
        c.circle(left + 3 * mm, y - 4.5 * mm, 2 * mm, fill=1, stroke=0)
        
        c.setFillColor(HexColor('#ffffff'))
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(left + 3 * mm, y - 5.5 * mm, str(i))
        
        c.setFillColor(HexColor('#0f172a'))
        c.setFont('Helvetica-Bold', 10)
        c.drawString(left + 7 * mm, y - 4 * mm, s.get('title', ''))
        
        c.setFillColor(HexColor('#475569'))
        c.setFont('Helvetica', 9)
        c.drawString(left + 7 * mm, y - 7.5 * mm, f"→ {s.get('effect', '')}")
        
        y -= 11 * mm

    # ========== FAQ SECTION ==========
    ensure_space(35)
    subheading('❓ Frequently Asked Questions', color='#7c3aed')
    
    faqs = [
        ('Is this a cost estimator or quotation?', 
         'No. This tool does not provide prices or bills of quantities. It analyzes realistic progression patterns based on global construction data.'),
        ('Why does my project stop at this phase?', 
         'International data shows similar projects often exhaust resources at this stage due to accumulated complexity and continuity challenges.'),
        ('Does this work for my country?', 
         'Yes. The analysis uses universal construction realities and patterns, not location-specific pricing.'),
        ('Why are floors and materials critical?', 
         'They exponentially multiply complexity, timeline requirements, and risk factors throughout the project lifecycle.'),
        ('Why no exact cost figures?', 
         'Strategic planning requires clarity and realistic expectations, not false precision that creates unrealistic expectations.'),
        ('Can this replace professional consultation?', 
         'No. This tool helps you make informed decisions before engaging architects, engineers, and contractors.')
    ]
    
    for question, answer in faqs:
        ensure_space(16)
        
        # Question
        c.setFillColor(HexColor('#f5f3ff'))
        c.roundRect(left, y - 13 * mm, w - left - right, 13 * mm, 2 * mm, fill=1, stroke=0)
        
        c.setFillColor(HexColor('#7c3aed'))
        c.setFont('Helvetica-Bold', 10)
        c.drawString(left + 3 * mm, y - 4 * mm, f'Q: {question}')
        
        # Answer
        c.setFillColor(HexColor('#475569'))
        c.setFont('Helvetica', 9)
        
        # Wrap answer text
        max_w = w - left - right - 6 * mm
        words = answer.split(' ')
        line = ''
        line_y = y - 8 * mm
        
        for word in words:
            test = (line + ' ' + word).strip()
            if c.stringWidth(test, 'Helvetica', 9) > max_w and line:
                c.drawString(left + 3 * mm, line_y, line)
                line_y -= 3.5 * mm
                line = word
            else:
                line = test
        
        if line:
            c.drawString(left + 3 * mm, line_y, line)
        
        y -= 15 * mm

    # ========== DISCLAIMER & FOOTER ==========
    ensure_space(35)
    subheading('⚖️ Important Legal Disclaimer', color='#64748b')
    
    c.setFillColor(HexColor('#f8fafc'))
    c.roundRect(left, y - 22 * mm, w - left - right, 22 * mm, 3 * mm, fill=1, stroke=0)
    
    c.setFillColor(HexColor('#0f172a'))
    c.setFont('Helvetica-Bold', 9)
    c.drawString(left + 3 * mm, y - 4 * mm, 'Professional Guidance Required')
    
    c.setFont('Helvetica', 8.5)
    c.setFillColor(HexColor('#475569'))
    text_y = y - 8 * mm
    
    disclaimer_lines = [
        'This report is an indicative simulation based on international construction data and patterns.',
        'It is NOT a quotation, cost estimate, building permit, or substitute for professional architectural,',
        'engineering, or construction management services. Always consult licensed professionals before',
        'making construction decisions. Results are educational and advisory in nature.'
    ]
    
    for line in disclaimer_lines:
        c.drawString(left + 3 * mm, text_y, line)
        text_y -= 3.8 * mm
    
    y -= 25 * mm
    
    # Final branding footer
    ensure_space(20)
    
    c.setFillColor(HexColor('#1e3a8a'))
    c.roundRect(left, y - 15 * mm, w - left - right, 15 * mm, 2 * mm, fill=1, stroke=0)
    
    c.setFillColor(HexColor('#ffffff'))
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(w / 2, y - 6 * mm, '✓ FREE Report Generated by MyFreeHousePlans.com')
    
    c.setFont('Helvetica', 9)
    c.drawCentredString(w / 2, y - 10 * mm, 'Visit www.MyFreeHousePlans.com for more free construction planning tools')
    
    c.save()
    return buf.getvalue()


def _reportlab_minimal(*, result) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor, Color

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    x = 20 * mm
    y = h - 25 * mm

    def draw_header():
        c.saveState()
        c.setFillColor(HexColor('#1e3a8a'))
        c.rect(0, h - 15 * mm, w, 15 * mm, fill=1, stroke=0)
        c.setFillColor(HexColor('#ffffff'))
        c.setFont('Helvetica-Bold', 11)
        c.drawString(x, h - 9 * mm, 'MyFreeHousePlans.com')
        c.setFont('Helvetica', 8)
        c.drawString(x, h - 12 * mm, 'Construction Intelligence Report')
        c.restoreState()

    def draw_watermark():
        c.saveState()
        try:
            c.setFillAlpha(0.05)
        except Exception:
            pass
        c.setFillColor(Color(0.1, 0.2, 0.5, alpha=0.05))
        c.setFont('Helvetica', 28)
        c.translate(w / 2, h / 2)
        c.rotate(45)
        text = 'MyFreeHousePlans.com'
        for x_offset in range(-500, 501, 250):
            for y_offset in range(-400, 401, 150):
                c.drawString(x_offset, y_offset, text)
        c.restoreState()

    c.setTitle('Construction Progress Intelligence Report - MyFreeHousePlans.com')
    draw_header()
    draw_watermark()
    
    y = h - 25 * mm
    
    c.setFillColor(HexColor('#1e3a8a'))
    c.roundRect(x - 5 * mm, y - 25 * mm, w - 2 * x + 10 * mm, 25 * mm, 4 * mm, fill=1, stroke=0)
    
    c.setFillColor(HexColor('#ffffff'))
    c.setFont('Helvetica-Bold', 20)
    c.drawString(x, y - 10 * mm, 'Construction Progress')
    c.drawString(x, y - 17 * mm, 'Intelligence Report')

    y -= 35 * mm
    c.setFillColor(HexColor('#475569'))
    c.setFont('Helvetica', 10)
    c.drawString(x, y, 'FREE Professional Analysis • Generated by MyFreeHousePlans.com')

    y -= 15 * mm
    c.setFillColor(HexColor('#dc2626'))
    c.setFont('Helvetica-Bold', 14)
    c.drawString(x, y, f"Critical Stopping Point: {result.stopping_phase}")

    y -= 12 * mm
    c.setFillColor(HexColor('#0f172a'))
    c.setFont('Helvetica-Bold', 11)
    c.drawString(x, y, 'Phase Analysis:')
    
    y -= 8 * mm
    c.setFont('Helvetica', 10)
    for st in result.statuses:
        if y < 30 * mm:
            c.showPage()
            draw_header()
            draw_watermark()
            y = h - 25 * mm
        
        status_color = '#10b981' if st.status == 'green' else ('#f59e0b' if st.status == 'orange' else '#ef4444')
        c.setFillColor(HexColor(status_color))
        c.drawString(x, y, f"● {st.phase}: {st.status.upper()}")
        c.setFillColor(HexColor('#475569'))
        c.setFont('Helvetica', 9)
        y -= 4 * mm
        c.drawString(x + 5 * mm, y, st.note)
        c.setFont('Helvetica', 10)
        y -= 7 * mm

    # Footer
    c.showPage()
    draw_header()
    draw_watermark()
    
    y = h / 2
    c.setFillColor(HexColor('#1e3a8a'))
    c.roundRect(x, y - 15 * mm, w - 2 * x, 15 * mm, 2 * mm, fill=1, stroke=0)
    
    c.setFillColor(HexColor('#ffffff'))
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(w / 2, y - 6 * mm, '✓ FREE Report • MyFreeHousePlans.com')
    c.setFont('Helvetica', 9)
    c.drawCentredString(w / 2, y - 10 * mm, 'Visit www.MyFreeHousePlans.com for more planning tools')
    
    c.save()
    return buf.getvalue()
