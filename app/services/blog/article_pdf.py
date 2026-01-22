from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from io import BytesIO
from pathlib import Path
from typing import Any

from flask import current_app


@dataclass(frozen=True)
class ArticlePdfInput:
    title: str
    slug: str
    created_at: datetime
    canonical_url: str
    content_html: str
    cover_image: str | None
    extras: dict[str, Any]


_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style)\b.*?>.*?</\1>")


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[\t\f\v]+", " ", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()


def _html_to_text(html: str) -> str:
    """Very small HTML->text converter (no extra deps).

    We keep headings, lists, and paragraphs reasonably readable for PDF output.
    """

    if not html:
        return ""

    cleaned = _SCRIPT_STYLE_RE.sub("", html)

    # Headings -> section separators
    cleaned = re.sub(r"(?is)<h2\b[^>]*>(.*?)</h2>", r"\n\n## \1\n", cleaned)
    cleaned = re.sub(r"(?is)<h3\b[^>]*>(.*?)</h3>", r"\n\n### \1\n", cleaned)
    cleaned = re.sub(r"(?is)<h4\b[^>]*>(.*?)</h4>", r"\n\n#### \1\n", cleaned)

    # Lists
    cleaned = re.sub(r"(?is)</li>", "\n", cleaned)
    cleaned = re.sub(r"(?is)<li\b[^>]*>", "• ", cleaned)
    cleaned = re.sub(r"(?is)</(ul|ol)>", "\n", cleaned)

    # Paragraph / breaks
    cleaned = re.sub(r"(?is)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?is)</p>", "\n\n", cleaned)

    # Links: keep label + url
    cleaned = re.sub(
        r"(?is)<a\b[^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",
        r"\2 (\1)",
        cleaned,
    )

    # Drop remaining tags
    cleaned = _TAG_RE.sub("", cleaned)

    return _normalize_whitespace(unescape(cleaned))


def _resolve_static_path(value: str) -> Path | None:
    if not value:
        return None

    rel = str(value).strip().lstrip("/\\")
    rel = rel.replace("\\", "/")
    if rel.lower().startswith("static/"):
        rel = rel[7:]

    static_folder = getattr(current_app, "static_folder", None)
    if not static_folder:
        return None

    candidate = Path(static_folder, rel).resolve()
    static_root = Path(static_folder).resolve()
    try:
        if Path(*candidate.parts[: len(static_root.parts)]) != static_root:
            return None
    except Exception:
        return None

    if candidate.is_file():
        return candidate
    return None


def build_article_pdf(inp: ArticlePdfInput) -> bytes:
    """Generate a branded, readable PDF for a blog article."""

    from reportlab.lib.colors import Color, HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    left = 18 * mm
    right = 18 * mm
    top = 18 * mm
    bottom = 18 * mm
    y = h - top

    brand = "www.myfreehouseplans.com"
    site_title = "MyFreeHousePlans"

    def draw_watermark() -> None:
        c.saveState()
        try:
            c.setFillAlpha(0.06)
        except Exception:
            pass
        c.setFillColor(Color(0.15, 0.18, 0.25, alpha=0.06))
        c.setFont("Times-Roman", 24)
        c.translate(w / 2, h / 2)
        c.rotate(35)
        for x in range(-520, 521, 260):
            for y_off in range(-420, 421, 160):
                c.drawString(x, y_off, brand)
        c.restoreState()

    def footer() -> None:
        c.saveState()
        c.setFillColor(HexColor("#64748b"))
        c.setFont("Helvetica", 9)
        c.drawString(left, bottom - 6 * mm, brand)
        c.drawRightString(w - right, bottom - 6 * mm, f"Page {c.getPageNumber()}")
        c.restoreState()

    def new_page() -> None:
        nonlocal y
        footer()
        c.showPage()
        y = h - top
        draw_watermark()

    def ensure_space(mm_needed: float) -> None:
        nonlocal y
        if y - (mm_needed * mm) < bottom + 10 * mm:
            new_page()

    def line(text: str, *, font: str = "Helvetica", size: int = 11, color: str = "#0b1220") -> None:
        nonlocal y
        ensure_space(7)
        c.setFillColor(HexColor(color))
        c.setFont(font, size)
        c.drawString(left, y, text)
        y -= 5.5 * mm

    def paragraph(text: str, *, font: str = "Helvetica", size: int = 11, color: str = "#111827") -> None:
        nonlocal y
        max_width = w - left - right
        c.setFillColor(HexColor(color))
        c.setFont(font, size)
        words = str(text).split(" ")
        current = ""
        for word in words:
            cand = (current + " " + word).strip()
            if c.stringWidth(cand, font, size) > max_width and current:
                ensure_space(7)
                c.drawString(left, y, current)
                y -= 5.2 * mm
                current = word
            else:
                current = cand
        if current:
            ensure_space(7)
            c.drawString(left, y, current)
            y -= 5.2 * mm

    def hr() -> None:
        nonlocal y
        ensure_space(6)
        c.setStrokeColor(HexColor("#e2e8f0"))
        c.setLineWidth(1)
        c.line(left, y, w - right, y)
        y -= 6 * mm

    def heading(text: str) -> None:
        nonlocal y
        ensure_space(10)
        c.setFillColor(HexColor("#0b1220"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(left, y, text)
        y -= 9 * mm

    def subheading(text: str) -> None:
        nonlocal y
        ensure_space(9)
        c.setFillColor(HexColor("#0b1220"))
        c.setFont("Helvetica-Bold", 13)
        c.drawString(left, y, text)
        y -= 7 * mm

    # First page
    draw_watermark()

    # Brand header
    c.saveState()
    c.setFillColor(HexColor("#1f4ce4"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, site_title)
    c.setFillColor(HexColor("#64748b"))
    c.setFont("Helvetica", 9)
    c.drawRightString(w - right, y + 1, brand)
    c.restoreState()
    y -= 8 * mm

    # Title + meta
    heading(inp.title)
    paragraph(inp.created_at.strftime("%B %d, %Y"), size=10, color="#475569")
    paragraph(f"Original article: {inp.canonical_url}", size=9, color="#475569")

    hr()

    # Optional cover image (local only)
    cover_path = None
    if inp.cover_image and not str(inp.cover_image).strip().lower().startswith(("http://", "https://")):
        cover_path = _resolve_static_path(inp.cover_image)

    if cover_path:
        try:
            ensure_space(70)
            img = ImageReader(str(cover_path))
            box_w = w - left - right
            box_h = 70 * mm
            c.drawImage(img, left, y - box_h, width=box_w, height=box_h, preserveAspectRatio=True, anchor="c")
            y -= box_h + 6 * mm
        except Exception:
            # Skip cover if it fails to render
            pass

    # Intro / about
    subheading("About this PDF")
    paragraph(
        "This document was generated from the article you are reading on MyFreeHousePlans. "
        "It keeps the key content in a clean, printable format.",
        size=10,
        color="#334155",
    )
    paragraph(
        "Visit www.myfreehouseplans.com for premium house plans, design tools, and construction insights.",
        size=10,
        color="#334155",
    )

    hr()

    # Main content
    subheading("Article")
    text = _html_to_text(inp.content_html)
    if not text:
        paragraph("(No article content)", size=10, color="#475569")
    else:
        for block in text.split("\n\n"):
            block = block.strip()
            if not block:
                continue

            if block.startswith("## "):
                subheading(block[3:].strip())
                continue
            if block.startswith("### "):
                ensure_space(9)
                c.setFillColor(HexColor("#0b1220"))
                c.setFont("Helvetica-Bold", 11)
                c.drawString(left, y, block[4:].strip())
                y -= 6.5 * mm
                continue

            paragraph(block, size=11, color="#111827")
            y -= 1.5 * mm

    # FAQ (if present)
    faq = (inp.extras or {}).get("faq") or []
    if isinstance(faq, list) and faq:
        new_page()
        subheading("FAQ")
        for item in faq:
            q = (item or {}).get("question")
            a = (item or {}).get("answer")
            if not q or not a:
                continue
            ensure_space(10)
            paragraph(f"Q: {str(q).strip()}", font="Helvetica-Bold", size=11, color="#0b1220")
            paragraph(_html_to_text(str(a)), size=10, color="#334155")
            y -= 2 * mm

    # Footer note / disclaimer
    ensure_space(18)
    hr()
    paragraph(
        "Disclaimer: This PDF is informational and reflects the article content at the time of generation. "
        "For the latest version, refer to the original article link above.",
        size=9,
        color="#64748b",
    )

    footer()
    c.save()
    return buf.getvalue()
