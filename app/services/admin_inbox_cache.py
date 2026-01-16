from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from flask import current_app

from app.extensions import db
from app.models import ContactMessage
from app.utils.ttl_cache import TTLCache


_COUNTS_CACHE: TTLCache[str, dict[str, int]] = TTLCache(ttl_seconds=30, max_items=64)
_EXECUTOR: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)


def invalidate_inbox_counts_cache() -> None:
    _COUNTS_CACHE.clear()


def _compute_counts() -> dict[str, int]:
    rows = db.session.query(ContactMessage.status, db.func.count(ContactMessage.id)).group_by(ContactMessage.status).all()
    by_status: dict[str, int] = {str(status): int(count or 0) for status, count in rows}

    open_count = int(by_status.get(ContactMessage.STATUS_NEW, 0) + by_status.get(ContactMessage.STATUS_IN_PROGRESS, 0))
    all_count = int(sum(by_status.values()))

    return {
        'all': all_count,
        'open': open_count,
        ContactMessage.STATUS_NEW: int(by_status.get(ContactMessage.STATUS_NEW, 0)),
        ContactMessage.STATUS_IN_PROGRESS: int(by_status.get(ContactMessage.STATUS_IN_PROGRESS, 0)),
        ContactMessage.STATUS_RESPONDED: int(by_status.get(ContactMessage.STATUS_RESPONDED, 0)),
        ContactMessage.STATUS_ARCHIVED: int(by_status.get(ContactMessage.STATUS_ARCHIVED, 0)),
    }


def get_inbox_counts_cached() -> dict[str, int]:
    return _COUNTS_CACHE.get_or_set('counts', _compute_counts, ttl_seconds=30)


def refresh_inbox_counts_async() -> None:
    """Best-effort async refresh for inbox counts.

    Keeps the UI snappy when large datasets make counts expensive.
    """

    try:
        app = current_app._get_current_object()
    except Exception:
        return

    def _job() -> dict[str, int]:
        with app.app_context():
            try:
                data = _compute_counts()
                _COUNTS_CACHE.set('counts', data, ttl_seconds=30)
                return data
            finally:
                try:
                    db.session.remove()
                except Exception:
                    pass

    try:
        _EXECUTOR.submit(_job)
    except Exception:
        # Never block a request if the executor is unavailable.
        return
