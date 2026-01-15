"""Fail-safe GeoIP lookup utilities (read-only)."""

from __future__ import annotations

import os
from functools import lru_cache
from ipaddress import ip_address
from typing import Mapping

try:
    import geoip2.database
    from geoip2.errors import AddressNotFoundError
except Exception:  # pragma: no cover - optional dependency
    geoip2 = None
    AddressNotFoundError = Exception


_reader = None
_reader_error = None


def init_geoip_reader(db_path: str | None, logger=None):
    """Initialize the GeoLite2 reader once (fail-safe)."""
    global _reader, _reader_error
    if _reader or _reader_error:
        return _reader
    if not db_path:
        _reader_error = 'GeoIP database path not configured.'
        return None
    if not os.path.exists(db_path):
        _reader_error = f'GeoIP database not found at {db_path}'
        if logger:
            try:
                logger.warning(_reader_error)
            except Exception:
                pass
        return None
    if geoip2 is None:
        _reader_error = 'geoip2 library not installed.'
        if logger:
            try:
                logger.warning(_reader_error)
            except Exception:
                pass
        return None
    try:
        _reader = geoip2.database.Reader(db_path)
    except Exception as exc:  # pragma: no cover - defensive
        _reader_error = f'GeoIP reader init failed: {exc}'
        if logger:
            try:
                logger.warning(_reader_error, exc_info=True)
            except Exception:
                pass
        _reader = None
    return _reader


def _normalize_ip(value: str | None) -> str | None:
    if not value:
        return None
    candidate = str(value).strip().strip('"').strip("'")
    if not candidate or candidate.lower() == 'unknown':
        return None
    if candidate.startswith('[') and ']' in candidate:
        candidate = candidate[1:candidate.index(']')]
    if candidate.count(':') == 1 and candidate.count('.') == 3:
        candidate = candidate.split(':', 1)[0]
    try:
        ip_address(candidate)
    except Exception:
        return None
    return candidate


def _select_best_ip(values: list[str | None]) -> str | None:
    first_valid = None
    for value in values:
        normalized = _normalize_ip(value)
        if not normalized:
            continue
        try:
            parsed = ip_address(normalized)
        except Exception:
            continue
        if parsed.is_global:
            return str(parsed)
        if first_valid is None and not parsed.is_unspecified:
            first_valid = str(parsed)
    return first_valid


def _forwarded_for_ips(header_value: str | None) -> list[str]:
    if not header_value:
        return []
    return [part.strip() for part in header_value.split(',') if part.strip()]


def _forwarded_header_ips(header_value: str | None) -> list[str]:
    if not header_value:
        return []
    ips: list[str] = []
    for part in header_value.split(','):
        seg = part.strip()
        if not seg:
            continue
        for token in seg.split(';'):
            token = token.strip()
            if not token.lower().startswith('for='):
                continue
            value = token[4:].strip().strip('"').strip("'")
            if value:
                ips.append(value)
    return ips


def resolve_client_ip(headers: Mapping[str, str], remote_addr: str | None) -> str | None:
    """Resolve client IP in a proxy-safe, IPv4/IPv6-aware way."""
    if headers is None:
        headers = {}

    primary_headers = [
        'CF-Connecting-IP',
        'True-Client-IP',
        'X-Real-IP',
        'X-Client-IP',
        'Fastly-Client-IP',
        'X-Cluster-Client-IP',
    ]
    primary_values = [headers.get(h) for h in primary_headers if headers.get(h)]
    chosen = _select_best_ip(primary_values)
    if chosen:
        return chosen

    forwarded_for = _forwarded_for_ips(headers.get('X-Forwarded-For'))
    chosen = _select_best_ip(forwarded_for)
    if chosen:
        return chosen

    forwarded = _forwarded_header_ips(headers.get('Forwarded'))
    chosen = _select_best_ip(forwarded)
    if chosen:
        return chosen

    fallback = headers.get('X-Forwarded')
    chosen = _select_best_ip([fallback])
    if chosen:
        return chosen

    return _select_best_ip([remote_addr]) or remote_addr


@lru_cache(maxsize=2048)
def get_country_for_ip(ip: str | None) -> str:
    """Return country name for IP (fail-safe, read-only)."""
    normalized = _normalize_ip(ip)
    if not normalized:
        return 'Unknown country'
    try:
        parsed = ip_address(normalized)
        if not parsed.is_global:
            return 'Unknown country'
    except Exception:
        return 'Unknown country'
    if _reader is None:
        return 'Unknown country'
    try:
        response = _reader.country(normalized)
        return response.country.name or 'Unknown country'
    except AddressNotFoundError:
        return 'Unknown country'
    except Exception:
        return 'Unknown country'
