"""Utilities for enriching per-request visitor tracking."""

from flask import g


def tag_visit_identity(name=None, email=None):
    """Attach optional identity data to the current visit payload."""
    payload = getattr(g, 'visit_track', None)
    if not payload:
        return
    if name:
        payload['name'] = name.strip()[:120]
    if email:
        payload['email'] = email.strip()[:200]
