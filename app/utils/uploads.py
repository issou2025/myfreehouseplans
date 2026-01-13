"""Shared helpers for safely persisting user uploads."""

from __future__ import annotations

import os
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.utils.storage import upload_to_cloud


# MIME type whitelist for security (extension spoofing prevention)
SAFE_MIME_TYPES = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/gif': ['.gif'],
    'image/webp': ['.webp'],
    'application/pdf': ['.pdf'],
    'application/dwg': ['.dwg'],
    'application/x-autocad': ['.dwg'],
    'application/msword': ['.doc'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
}


def _validate_file_content(file: FileStorage, filename: str) -> None:
    """
    Validate file content matches its claimed extension.
    
    This prevents attacks where malicious files are renamed to safe extensions.
    """
    # Read first 8KB to determine MIME type
    stream = file.stream
    original_pos = stream.tell()
    stream.seek(0)
    header = stream.read(8192)
    stream.seek(original_pos)
    
    # Guess MIME type from content (magic bytes)
    guessed_mime, _ = mimetypes.guess_type(filename)
    
    # Additional magic byte validation for common formats
    if header.startswith(b'%PDF'):
        actual_mime = 'application/pdf'
    elif header.startswith(b'\xff\xd8\xff'):
        actual_mime = 'image/jpeg'
    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
        actual_mime = 'image/png'
    elif header.startswith(b'GIF89a') or header.startswith(b'GIF87a'):
        actual_mime = 'image/gif'
    elif header.startswith(b'RIFF') and b'WEBP' in header[:32]:
        actual_mime = 'image/webp'
    else:
        actual_mime = guessed_mime
    
    if actual_mime not in SAFE_MIME_TYPES:
        raise ValueError(
            f'File content type ({actual_mime}) is not allowed. '
            'Only images, PDFs, and documents are permitted.'
        )
    
    ext = '.' + filename.rsplit('.', 1)[1].lower()
    valid_extensions = SAFE_MIME_TYPES.get(actual_mime, [])
    
    if ext not in valid_extensions:
        raise ValueError(
            f'File extension {ext} does not match content type {actual_mime}. '
            'This may indicate a renamed malicious file.'
        )


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
    """Persist an incoming file after rigorous security validation.
    
    Security measures:
    - Validates file extension against whitelist
    - Validates MIME type from file content (magic bytes)
    - Prevents double-extension attacks (.pdf.exe)
    - Enforces file size limits
    - Sanitizes filenames to prevent path traversal
    - Validates folder names to prevent directory traversal
    
    Returns the relative path (folder/filename) suitable for storing in the DB.
    """

    if file is None:
        return None

    if not hasattr(file, 'filename') or not file.filename:
        raise ValueError('Invalid upload object provided. Please reselect the file and try again.')

    # Sanitize and validate filename
    # NOTE: secure_filename() keeps dots. We collapse extra dots in the basename
    # so users can upload names like "plan.v2.final.jpg" without triggering a
    # false-positive "multiple extensions" rejection.
    filename = secure_filename(file.filename)
    if not filename or '.' not in filename:
        raise ValueError('The uploaded file must include a valid filename and extension.')

    base, ext_part = filename.rsplit('.', 1)
    ext_part = ext_part.lower()
    # Collapse any remaining dots in the base name to avoid ambiguous names.
    base = (base or 'upload').replace('.', '_')
    filename = f"{base}.{ext_part}"

    ext = filename.rsplit('.', 1)[1].lower()
    allowed = allowed_extensions or current_app.config.get('ALLOWED_EXTENSIONS', set())
    if allowed and ext not in {e.lower() for e in allowed}:
        raise ValueError(
            f'File type .{ext} is not allowed. '
            f'Allowed types: {", ".join(sorted(allowed))}'
        )
    
    # Validate MIME type matches extension (prevents renamed malicious files)
    _validate_file_content(file, filename)

    # Enforce file size limit
    size_limit = _max_size()
    if size_limit:
        stream = file.stream
        if hasattr(stream, 'seek'):
            original_pos = stream.tell()
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(original_pos)
            
            if size > size_limit:
                size_mb = size / (1024 * 1024)
                limit_mb = size_limit / (1024 * 1024)
                raise ValueError(
                    f'File too large ({size_mb:.1f} MB). '
                    f'Maximum allowed size is {limit_mb:.1f} MB.'
                )
    
    # Sanitize folder name to prevent path traversal
    folder = secure_filename(folder)
    if not folder or folder == '.' or folder == '..':
        folder = 'uploads'

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

    return os.path.join('uploads', folder, safe_name).replace('\\', '/')


def resolve_protected_upload(relative_path: str) -> Path:
    """Return a normalized absolute Path inside the protected upload root.

    Accepts historical values that may start with ``uploads/`` and prevents
    directory traversal by ensuring the final path remains within the
    configured protected folder.
    """

    if not relative_path:
        raise ValueError('No file path was provided.')

    base_dir = current_app.config.get('PROTECTED_UPLOAD_FOLDER') or current_app.config['UPLOAD_FOLDER']
    base_path = Path(base_dir).resolve()

    clean_relative = str(relative_path).strip().lstrip('/\\')
    if not clean_relative:
        raise ValueError('Empty file path received.')

    parts = [part for part in Path(clean_relative).parts if part not in ('', '.', '..')]
    if parts and parts[0].lower() == 'uploads':
        parts = parts[1:]
    if not parts:
        raise ValueError('Unable to resolve file path inside protected uploads.')

    candidate = base_path.joinpath(*parts).resolve()
    if os.path.commonpath([str(base_path), str(candidate)]) != str(base_path):
        raise ValueError('File path escapes protected upload directory.')

    return candidate
