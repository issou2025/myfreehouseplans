"""Request tracking with signal-over-noise principles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, date
from collections import deque
from threading import Lock

from flask import current_app

from sqlalchemy import insert, inspect

from app.extensions import db
from app.models import RecentLog


@dataclass
class AnalyticsEvent:
    timestamp: datetime
    ip_address: str
    country_code: str
    country_name: str
    request_path: str
    user_agent: str
    traffic_type: str  # human|bot|attack
    is_search_bot: bool = False
    device: str = ''
    method: str = ''
    status_code: int | None = None
    response_time_ms: float | None = None
    referrer: str | None = None
    session_id: str | None = None


# Dedupe cache to reduce bot log writes.
_lock = Lock()
_bot_last_logged: dict[str, datetime] = {}

# In-memory last-N event buffer (per-process) to keep the admin UI useful even
# when migrations are pending or the DB is temporarily unavailable.
_recent_events_lock = Lock()
_recent_events = deque(maxlen=1000)

_recent_log_columns: set[str] | None = None
_recent_log_columns_checked_at: datetime | None = None
_recent_log_columns_ttl_seconds = 60


def _get_recent_log_columns() -> set[str] | None:
    global _recent_log_columns, _recent_log_columns_checked_at

    now = datetime.utcnow()
    if _recent_log_columns_checked_at is not None:
        age = (now - _recent_log_columns_checked_at).total_seconds()
        if age < _recent_log_columns_ttl_seconds:
            return _recent_log_columns

    try:
        inspector = inspect(db.engine)
        if not inspector.has_table('recent_logs'):
            _recent_log_columns = None
        else:
            _recent_log_columns = {col['name'] for col in inspector.get_columns('recent_logs')}
    except Exception:
        _recent_log_columns = None

    _recent_log_columns_checked_at = now
    return _recent_log_columns


def _should_log_bot(*, ip: str, ua: str, is_search_bot: bool, now: datetime) -> bool:
    if not is_search_bot and not current_app.config.get('ANALYTICS_LOG_GENERIC_BOTS', False):
        return False

    # Known search bots are valuable; still dedupe aggressively to limit DB writes.
    key = f"{ip}|{(ua or '')[:80].lower()}"
    window_seconds = int(current_app.config.get('ANALYTICS_BOT_DEDUPE_SECONDS', 3600) or 3600)
    cutoff = now - timedelta(seconds=window_seconds)

    with _lock:
        last = _bot_last_logged.get(key)
        if last is not None and last > cutoff:
            return False
        _bot_last_logged[key] = now
        # Best-effort cleanup to prevent unbounded growth.
        if len(_bot_last_logged) > 5000:
            for k, ts in list(_bot_last_logged.items())[:1000]:
                if ts <= cutoff:
                    _bot_last_logged.pop(k, None)
    return True


def record_event(event: AnalyticsEvent) -> None:
    """Persist only useful events into RecentLog."""

    now = event.timestamp
    traffic = (event.traffic_type or '').strip().lower()

    if traffic == 'attack':
        # Attacks are aggregated, not fully logged.
        return

    if traffic == 'bot':
        if not _should_log_bot(ip=event.ip_address, ua=event.user_agent, is_search_bot=event.is_search_bot, now=now):
            return

    # Humans are always logged (short retention window).
    payload = {
        'ip_address': event.ip_address,
        'country_code': event.country_code or None,
        'country_name': event.country_name or None,
        'request_path': (event.request_path or '/')[:255],
        'user_agent': (event.user_agent or '')[:500],
        'device': (event.device or '')[:32] or None,
        'method': (event.method or '')[:12] or None,
        'status_code': event.status_code,
        'response_time_ms': event.response_time_ms,
        'referrer': (event.referrer or '')[:500] or None,
        'session_id': (event.session_id or '')[:120] or None,
        'traffic_type': traffic,
        'is_search_bot': bool(event.is_search_bot),
        'timestamp': now,
    }

    # Always keep a best-effort copy in memory for admin live view.
    try:
        with _recent_events_lock:
            _recent_events.append(
                {
                    'timestamp': now,
                    'traffic_type': traffic,
                    'is_search_bot': bool(event.is_search_bot),
                    'ip_address': event.ip_address,
                    'country_code': event.country_code or '',
                    'country_name': event.country_name or '',
                    'request_path': payload.get('request_path') or '/',
                    'method': payload.get('method') or '',
                    'status_code': payload.get('status_code'),
                    'response_time_ms': payload.get('response_time_ms'),
                    'user_agent': payload.get('user_agent') or '',
                    'device': payload.get('device') or '',
                    'referrer': payload.get('referrer'),
                    'session_id': payload.get('session_id'),
                }
            )
    except Exception:
        pass

    # Only insert columns that actually exist in the DB (handles partial migrations).
    columns = _get_recent_log_columns()
    if not columns:
        return

    payload = {key: value for key, value in payload.items() if key in columns}
    if not payload:
        return

    # Use an engine-level transaction to avoid committing unrelated ORM work.
    try:
        with db.engine.begin() as conn:
            conn.execute(insert(RecentLog.__table__).values(**payload))
    except Exception:
        # Analytics must never break user requests.
        return


def peek_recent_events(
    *,
    limit: int = 50,
    since: datetime | None = None,
    traffic_type: str = 'human',
) -> list[dict]:
    """Return best-effort recent events from in-memory buffer.

    traffic_type supports: human | bot | crawler | all
    """

    limit = max(1, min(int(limit or 50), 500))
    tt = (traffic_type or 'human').strip().lower()
    if tt not in {'human', 'bot', 'crawler', 'all'}:
        tt = 'human'

    def _match(row: dict) -> bool:
        ts = row.get('timestamp')
        if since is not None and isinstance(ts, datetime) and ts < since:
            return False
        if tt == 'all':
            return True
        if tt == 'crawler':
            return row.get('traffic_type') == 'bot' and bool(row.get('is_search_bot'))
        return row.get('traffic_type') == tt

    try:
        with _recent_events_lock:
            rows = list(_recent_events)
    except Exception:
        rows = []

    selected = [r for r in rows if _match(r)]
    selected.sort(key=lambda r: r.get('timestamp') or datetime.min, reverse=True)
    return selected[:limit]


def safe_country_for_ip(ip: str) -> tuple[str, str]:
    """Return (country_code, country_name) with graceful fallback."""

    try:
        from app.utils.geoip import get_country_details_for_ip

        code, name = get_country_details_for_ip(ip)
    except Exception:
        return 'UN', 'Unknown'

    return code or 'UN', name or 'Unknown'
