"""Media URL helpers.

Fields like `cover_image` and `free_pdf_file` may store either:
- a relative path under app/static/uploads (legacy/local dev)
- a full https URL (cloud storage)

These helpers normalize that for templates and routes.
"""

from __future__ import annotations

from urllib.parse import urlparse

from flask import url_for


def is_absolute_url(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def upload_url(value: str | None) -> str | None:
    if not value:
        return None
    if is_absolute_url(value):
        return value
    return url_for("static", filename=value)
