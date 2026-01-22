from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from flask import current_app


@dataclass(frozen=True)
class ArticlePdfHtmlContext:
    title: str
    slug: str
    created_at: datetime
    canonical_url: str
    content_html: str
    cover_image: str | None
    extras: dict[str, Any]


_H2_RE = re.compile(r"(?is)<h2(?P<attrs>[^>]*)>(?P<body>.*?)</h2>")
_H3_RE = re.compile(r"(?is)<h3(?P<attrs>[^>]*)>(?P<body>.*?)</h3>")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _plain_text(html_fragment: str) -> str:
    text = _TAG_RE.sub("", html_fragment or "")
    text = _WS_RE.sub(" ", text).strip()
    return text


def static_file_uri(rel_path: str) -> str | None:
    if not rel_path:
        return None
    rel = str(rel_path).strip().lstrip("/\\")
    rel = rel.replace("\\", "/")
    if rel.lower().startswith("static/"):
        rel = rel[7:]

    static_folder = current_app.static_folder
    candidate = Path(static_folder, rel).resolve()
    static_root = Path(static_folder).resolve()

    try:
        if Path(*candidate.parts[: len(static_root.parts)]) != static_root:
            return None
    except Exception:
        return None

    if candidate.is_file():
        return candidate.as_uri()
    return None


def _rewrite_static_urls_for_weasyprint(html: str) -> str:
    """Convert /static/... and static/... URLs into file:// URIs for WeasyPrint."""

    if not html:
        return ""

    def rewrite_url(url: str) -> str | None:
        if not url:
            return None

        trimmed = url.strip()
        if trimmed.startswith(("http://", "https://", "data:")):
            return None

        # Only rewrite static paths.
        if trimmed.startswith("/static/"):
            rel = trimmed.lstrip("/")
        elif trimmed.startswith("static/"):
            rel = trimmed
        else:
            return None

        uri = static_file_uri(rel)
        return uri

    def repl_attr(match: re.Match[str]) -> str:
        attr = match.group(1)
        quote = match.group(2)
        url = match.group(3)
        replacement = rewrite_url(url)
        if not replacement:
            return match.group(0)
        return f"{attr}={quote}{replacement}{quote}"

    # src/href attributes only
    html = re.sub(r"(?i)\b(src|href)=(['\"])([^'\"]+)\2", repl_attr, html)
    return html


def build_toc_and_annotated_html(content_html: str) -> tuple[list[dict[str, str]], str]:
    """Extract H2/H3 headings, assign stable IDs, and return a TOC + updated HTML."""

    toc: list[dict[str, str]] = []

    section_counter = 0

    def handle_h2(match: re.Match[str]) -> str:
        nonlocal section_counter
        section_counter += 1
        text = _plain_text(match.group("body")) or f"Section {section_counter}"
        sec_id = f"sec-{section_counter}"
        toc.append({"level": "h2", "id": sec_id, "title": text})
        attrs = match.group("attrs") or ""
        if "id=" in attrs.lower():
            # leave existing id, but still add our toc entry using it
            existing = re.search(r"(?i)\bid=(['\"])(.*?)\1", attrs)
            if existing and existing.group(2):
                toc[-1]["id"] = existing.group(2)
                return match.group(0)
        return f"<h2 id=\"{sec_id}\"{attrs}>{match.group('body')}</h2>"

    def handle_h3(match: re.Match[str]) -> str:
        nonlocal section_counter
        text = _plain_text(match.group("body"))
        if not text:
            return match.group(0)
        sec_id = f"sec-{section_counter}-sub-{len([t for t in toc if t['level']=='h3' and t['id'].startswith(f'sec-{section_counter}-')]) + 1}"
        toc.append({"level": "h3", "id": sec_id, "title": text})
        attrs = match.group("attrs") or ""
        if "id=" in attrs.lower():
            existing = re.search(r"(?i)\bid=(['\"])(.*?)\1", attrs)
            if existing and existing.group(2):
                toc[-1]["id"] = existing.group(2)
                return match.group(0)
        return f"<h3 id=\"{sec_id}\"{attrs}>{match.group('body')}</h3>"

    updated = _H2_RE.sub(handle_h2, content_html or "")
    updated = _H3_RE.sub(handle_h3, updated)
    return toc, updated


def build_article_pdf_weasyprint(*, html: str, stylesheets: Iterable[Path]) -> bytes:
    """Render HTML to PDF using WeasyPrint if available."""

    try:
        from weasyprint import CSS, HTML  # type: ignore
    except Exception as exc:
        raise RuntimeError("WeasyPrint is not installed/available.") from exc

    # Rewrite /static/* references so it works without HTTP requests.
    html = _rewrite_static_urls_for_weasyprint(html)

    css_objs = [CSS(filename=str(p)) for p in stylesheets]

    # Use app root as base URL so relative links resolve to files.
    base_url = str(Path(current_app.root_path).resolve())
    return HTML(string=html, base_url=base_url).write_pdf(stylesheets=css_objs)
