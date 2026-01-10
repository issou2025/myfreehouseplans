"""Shared helpers for safely persisting user uploads."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable, Optional

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.utils.storage import upload_to_cloud


def _max_size() -> Optional[int]:
    try:
        return int(current_app.config.get('MAX_CONTENT_LENGTH') or 0)
    except (TypeError, ValueError):
        return None


def save_uploaded_file(
    file: Optional[FileStorage],
    folder: str = 'uploads',
    allowed_extensions: Optional[Iterable[str]] = None,
) -> Optional[str]:
    """Persist an incoming file after validating name, extension, and size.

    Returns the relative path (folder/filename) suitable for storing in the DB.
    The helper respects the ``PROTECTED_FOLDERS`` config entry to route sensitive
    files to the protected upload root.
    """

    if file is None:
        return None

    if not hasattr(file, 'filename'):
        raise ValueError('Invalid upload object provided. Please reselect the file and try again.')

    filename = secure_filename(file.filename or '')
    if not filename or '.' not in filename:
        raise ValueError('The uploaded file must include a valid filename and extension.')

    ext = filename.rsplit('.', 1)[1].lower()
    allowed = allowed_extensions or current_app.config.get('ALLOWED_EXTENSIONS', set())
    if allowed and ext not in {e.lower() for e in allowed}:
        raise ValueError('This file type is not allowed. Please upload a supported format.')

    size_limit = _max_size()
    stream = getattr(file, 'stream', None)
    if size_limit and stream and hasattr(stream, 'seek'):
        pos = stream.tell()
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(pos)
        if size > size_limit:
            raise ValueError('File too large. Please upload a file smaller than 16 MB.')

    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    safe_name = f"{timestamp}_{filename}"

    cloud_url = None
    try:
        cloud_url = upload_to_cloud(file, folder)
    except Exception as exc:
        try:
            current_app.logger.warning('Cloud upload failed; falling back to local storage: %s', exc)
        except Exception:
            pass
        cloud_url = None

    if cloud_url:
        return cloud_url

    protected_folders = current_app.config.get('PROTECTED_FOLDERS', {'pdfs'})
    if folder in protected_folders:
        base_upload = current_app.config.get('PROTECTED_UPLOAD_FOLDER')
    else:
        base_upload = current_app.config['UPLOAD_FOLDER']

    upload_path = os.path.join(base_upload, folder)
    os.makedirs(upload_path, exist_ok=True)

    absolute_path = os.path.join(upload_path, safe_name)
    file.save(absolute_path)

    return os.path.join(folder, safe_name).replace('\\', '/')
