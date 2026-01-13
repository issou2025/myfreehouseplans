"""Cloud storage helpers.

This module provides a thin abstraction for uploading user-provided files to a
cloud provider when configured (production), while keeping a local fallback for
development.

Supported providers:
- Cloudinary (recommended for Render): set CLOUDINARY_URL.

The upload functions return a public URL.
"""

from __future__ import annotations

import os
from typing import Optional

from flask import current_app
from werkzeug.datastructures import FileStorage


class CloudStorageConfigurationError(RuntimeError):
    """Raised when persistent storage credentials are missing."""


def _cloudinary_url() -> Optional[str]:
    return os.environ.get("CLOUDINARY_URL") or current_app.config.get("CLOUDINARY_URL")


def upload_to_cloud(file: FileStorage, folder: str) -> Optional[str]:
    """Upload a file to the configured cloud provider and return a URL."""

    if not file or not getattr(file, "filename", ""):
        return None

    cloudinary_url = _cloudinary_url()
    if not cloudinary_url:
        raise CloudStorageConfigurationError(
            "CLOUDINARY_URL is not configured. Persistent uploads are disabled."
        )

    import cloudinary
    import cloudinary.uploader

    cloudinary.config(cloudinary_url=cloudinary_url)

    # Ensure stream is at the beginning before handing off to the SDK.
    try:
        file.stream.seek(0)
    except Exception:
        pass

    filename = (file.filename or "upload").strip()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    resource_type = "image" if ext in {"png", "jpg", "jpeg", "gif", "webp", "avif"} else "raw"

    result = cloudinary.uploader.upload(
        file,
        folder=f"myfreehouseplans/{folder}",
        resource_type=resource_type,
        use_filename=True,
        unique_filename=True,
        overwrite=False,
    )

    secure_url = result.get("secure_url") or result.get("url")
    if not secure_url:
        raise RuntimeError("Cloudinary upload did not return a public URL.")
    return secure_url
