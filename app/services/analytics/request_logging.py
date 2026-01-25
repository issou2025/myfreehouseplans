"""Request logging helpers for real-time visitor and system logs."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any
import traceback

from sqlalchemy import insert

from app.extensions import db
from app.models import (
    VisitorLog,
    CrawlerLog,
    BotLog,
    ApiLog,
    AnalyzerLog,
    PerformanceLog,
    ErrorLog,
)


def _base_payload(event) -> dict[str, Any]:
    data = asdict(event)
    return {
        'timestamp': data.get('timestamp'),
        'ip_address': data.get('ip_address') or '0.0.0.0',
        'route': (data.get('request_path') or '/')[:255],
        'method': data.get('method') or None,
        'status_code': data.get('status_code') or None,
        'response_time_ms': data.get('response_time_ms') or None,
        'user_agent': (data.get('user_agent') or '')[:500],
        'device': (data.get('device') or '')[:32] or None,
        'country': (data.get('country_name') or data.get('country_code') or 'Unknown')[:80],
        'referrer': (data.get('referrer') or '')[:500] or None,
        'session_id': (data.get('session_id') or '')[:120] or None,
    }


def _safe_insert(table, payload: dict[str, Any]) -> None:
    try:
        with db.engine.begin() as conn:
            conn.execute(insert(table).values(**payload))
    except Exception:
        # Never break requests due to logging failures.
        return


def log_request(*, event, log_type: str) -> None:
    if event is None:
        return
    payload = _base_payload(event)
    table = None

    if log_type == 'visitor':
        table = VisitorLog.__table__
    elif log_type == 'crawler':
        table = CrawlerLog.__table__
    elif log_type == 'bot':
        table = BotLog.__table__
    elif log_type == 'api':
        table = ApiLog.__table__
    elif log_type == 'performance':
        table = PerformanceLog.__table__
    elif log_type == 'analyzer':
        table = AnalyzerLog.__table__

    if table is None:
        return

    _safe_insert(table, payload)


def log_analyzer_event(*, event, event_type: str, detail: str | None = None) -> None:
    if event is None:
        return
    payload = _base_payload(event)
    payload.update({
        'event_type': (event_type or 'event')[:40],
        'detail': (detail or '')[:800] if detail else None,
    })
    _safe_insert(AnalyzerLog.__table__, payload)


def log_error(*, event=None, error: Exception | None = None, status_code: int | None = None) -> None:
    payload: dict[str, Any]

    if event is not None:
        payload = _base_payload(event)
    else:
        payload = {
            'timestamp': datetime.utcnow(),
            'ip_address': '0.0.0.0',
            'route': '/',
            'method': None,
            'status_code': status_code,
            'response_time_ms': None,
            'user_agent': None,
            'device': None,
            'country': 'Unknown',
            'referrer': None,
            'session_id': None,
        }

    payload.update({
        'status_code': status_code or payload.get('status_code'),
        'error_type': (type(error).__name__ if error else 'Error'),
        'error_message': (str(error) if error else 'Unknown error')[:1000],
        'stacktrace': traceback.format_exc()[:4000] if error else None,
    })

    _safe_insert(ErrorLog.__table__, payload)
