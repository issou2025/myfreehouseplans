"""Media URL helpers.

Fields like `cover_image` and `free_pdf_file` may store either:
- a relative path under app/static/uploads (legacy/local dev)
- a full https URL (cloud storage)

These helpers normalize that for templates and routes.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from flask import current_app, url_for


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

    # Normalize common historical/path variants.
    rel = str(value).strip().lstrip('/\\')
    rel = rel.replace('\\', '/')
    if rel.lower().startswith('static/'):
        rel = rel[7:]

    static_folder = getattr(current_app, 'static_folder', None)
    placeholder_rel = current_app.config.get('IMAGE_PLACEHOLDER', 'images/placeholder.svg')

    if not static_folder:
        return url_for('static', filename=rel)

    # Build an absolute path and ensure it stays within the static folder.
    candidate = os.path.normpath(os.path.join(static_folder, rel))
    static_root = os.path.normpath(static_folder)
    try:
        if os.path.commonpath([static_root, candidate]) != static_root:
            return url_for('static', filename=placeholder_rel)
    except Exception:
        return url_for('static', filename=placeholder_rel)

    if not os.path.isfile(candidate):
        return url_for('static', filename=placeholder_rel)

    return url_for('static', filename=rel)
