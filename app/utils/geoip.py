"""Fail-safe GeoIP lookup utilities (read-only)."""

from __future__ import annotations

import json
import os
from ipaddress import ip_address, ip_network
from typing import Iterable, Mapping
from urllib.request import Request, urlopen

from app.utils.ttl_cache import TTLCache

try:
    import geoip2.database
    from geoip2.errors import AddressNotFoundError
except Exception:  # pragma: no cover - optional dependency
    geoip2 = None
    AddressNotFoundError = Exception


UNKNOWN_COUNTRY = 'Unknown'
UNKNOWN_COUNTRY_CODE = 'UN'

_reader = None
_reader_error = None

_fallback_enabled = True
_fallback_url_template = 'https://ipapi.co/{ip}/json/'
_fallback_timeout = 0.6
_cache_ttl_seconds = 86400
_negative_cache_ttl_seconds = 900

_country_cache = TTLCache[str, str](ttl_seconds=_cache_ttl_seconds, max_items=8192)
_country_details_cache = TTLCache[str, tuple[str, str]](ttl_seconds=_cache_ttl_seconds, max_items=8192)


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


def init_geoip_settings(
    *,
    fallback_enabled: bool | None = None,
    fallback_url_template: str | None = None,
    fallback_timeout: float | None = None,
    cache_ttl_seconds: int | None = None,
    negative_cache_ttl_seconds: int | None = None,
):
    """Configure GeoIP lookup behavior (optional)."""
    global _fallback_enabled, _fallback_url_template, _fallback_timeout
    global _cache_ttl_seconds, _negative_cache_ttl_seconds, _country_cache, _country_details_cache

    if fallback_enabled is not None:
        _fallback_enabled = bool(fallback_enabled)
    if fallback_url_template:
        _fallback_url_template = fallback_url_template
    if fallback_timeout is not None:
        try:
            _fallback_timeout = max(0.2, float(fallback_timeout))
        except Exception:
            pass
    if cache_ttl_seconds is not None:
        try:
            _cache_ttl_seconds = max(300, int(cache_ttl_seconds))
        except Exception:
            pass
    if negative_cache_ttl_seconds is not None:
        try:
            _negative_cache_ttl_seconds = max(60, int(negative_cache_ttl_seconds))
        except Exception:
            pass
    _country_cache = TTLCache[str, str](ttl_seconds=_cache_ttl_seconds, max_items=8192)
    _country_details_cache = TTLCache[str, tuple[str, str]](ttl_seconds=_cache_ttl_seconds, max_items=8192)


def _normalize_ip(value: str | None) -> str | None:
    if not value:
        return None
    candidate = str(value).strip().strip('"').strip("'")
    if not candidate or candidate.lower() == 'unknown':
        return None
    if '%' in candidate:
        candidate = candidate.split('%', 1)[0]
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


def parse_trusted_proxies(value: str | Iterable[str] | None) -> list:
    """Parse trusted proxy CIDRs/IPs from config or env."""
    if not value:
        return []
    if isinstance(value, str):
        items = [part.strip() for part in value.split(',') if part.strip()]
    else:
        items = [str(part).strip() for part in value if str(part).strip()]
    trusted = []
    for item in items:
        try:
            if '/' in item:
                trusted.append(ip_network(item, strict=False))
            else:
                suffix = '/128' if ':' in item else '/32'
                trusted.append(ip_network(f'{item}{suffix}', strict=False))
        except Exception:
            continue
    return trusted


def _is_trusted_proxy(remote_addr: str | None, trusted_proxies: list | None) -> bool:
    if not remote_addr:
        return True
    normalized = _normalize_ip(remote_addr)
    if not normalized:
        return False
    try:
        parsed = ip_address(normalized)
    except Exception:
        return False
    if parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_reserved:
        return True
    if not trusted_proxies:
        return False
    for network in trusted_proxies:
        try:
            if parsed in network:
                return True
        except Exception:
            continue
    return False


def resolve_client_ip(
    headers: Mapping[str, str],
    remote_addr: str | None,
    *,
    trusted_proxies: list | None = None,
) -> str | None:
    """Resolve client IP in a proxy-safe, IPv4/IPv6-aware way."""
    if headers is None:
        headers = {}

    trust_headers = _is_trusted_proxy(remote_addr, trusted_proxies)

    if trust_headers:
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


def _external_country_lookup(ip: str) -> str | None:
    if not _fallback_enabled:
        return None
    if not _fallback_url_template:
        return None
    url = _fallback_url_template.format(ip=ip)
    try:
        req = Request(url, headers={'User-Agent': 'myfreehouseplans-geoip/1.0'})
        with urlopen(req, timeout=_fallback_timeout) as response:
            payload = response.read().decode('utf-8', errors='ignore')
        data = json.loads(payload) if payload else {}
    except Exception:
        return None
    country = None
    if isinstance(data, dict):
        country = data.get('country_name') or data.get('country') or data.get('countryName')
    if not country or not isinstance(country, str):
        return None
    country = country.strip()
    if not country or country.lower() in {'unknown', 'undefined', 'n/a'}:
        return None
    return country


def get_country_for_ip(ip: str | None) -> str:
    """Return country name for IP (fail-safe, read-only)."""
    normalized = _normalize_ip(ip)
    if not normalized:
        return UNKNOWN_COUNTRY

    cached = _country_cache.get(normalized)
    if cached is not None:
        return cached

    try:
        parsed = ip_address(normalized)
        if not parsed.is_global:
            _country_cache.set(normalized, UNKNOWN_COUNTRY, ttl_seconds=_negative_cache_ttl_seconds)
            return UNKNOWN_COUNTRY
    except Exception:
        _country_cache.set(normalized, UNKNOWN_COUNTRY, ttl_seconds=_negative_cache_ttl_seconds)
        return UNKNOWN_COUNTRY

    if _reader is not None:
        try:
            response = _reader.country(normalized)
            name = response.country.name or UNKNOWN_COUNTRY
            ttl = _cache_ttl_seconds if name != UNKNOWN_COUNTRY else _negative_cache_ttl_seconds
            _country_cache.set(normalized, name, ttl_seconds=ttl)
            return name
        except AddressNotFoundError:
            pass
        except Exception:
            pass

    fallback = _external_country_lookup(normalized)
    if fallback:
        _country_cache.set(normalized, fallback, ttl_seconds=_cache_ttl_seconds)
        return fallback

    _country_cache.set(normalized, UNKNOWN_COUNTRY, ttl_seconds=_negative_cache_ttl_seconds)
    return UNKNOWN_COUNTRY


def get_country_details_for_ip(ip: str | None) -> tuple[str, str]:
    """Return (country_code, country_name) for IP (fail-safe, read-only)."""

    normalized = _normalize_ip(ip)
    if not normalized:
        return UNKNOWN_COUNTRY_CODE, UNKNOWN_COUNTRY

    cached = _country_details_cache.get(normalized)
    if cached is not None:
        return cached

    try:
        parsed = ip_address(normalized)
        if not parsed.is_global:
            value = (UNKNOWN_COUNTRY_CODE, UNKNOWN_COUNTRY)
            _country_details_cache.set(normalized, value, ttl_seconds=_negative_cache_ttl_seconds)
            return value
    except Exception:
        value = (UNKNOWN_COUNTRY_CODE, UNKNOWN_COUNTRY)
        _country_details_cache.set(normalized, value, ttl_seconds=_negative_cache_ttl_seconds)
        return value

    if _reader is not None:
        try:
            response = _reader.country(normalized)
            code = response.country.iso_code or UNKNOWN_COUNTRY_CODE
            name = response.country.name or UNKNOWN_COUNTRY
            if not isinstance(code, str):
                code = UNKNOWN_COUNTRY_CODE
            if not isinstance(name, str):
                name = UNKNOWN_COUNTRY
            code = code.strip() or UNKNOWN_COUNTRY_CODE
            name = name.strip() or UNKNOWN_COUNTRY
            ttl = _cache_ttl_seconds if name != UNKNOWN_COUNTRY else _negative_cache_ttl_seconds
            value = (code, name)
            _country_details_cache.set(normalized, value, ttl_seconds=ttl)
            return value
        except AddressNotFoundError:
            pass
        except Exception:
            pass

    # Fallback HTTP lookup only yields country name in our current parser.
    fallback = _external_country_lookup(normalized)
    if fallback:
        value = (UNKNOWN_COUNTRY_CODE, fallback)
        _country_details_cache.set(normalized, value, ttl_seconds=_cache_ttl_seconds)
        return value

    value = (UNKNOWN_COUNTRY_CODE, UNKNOWN_COUNTRY)
    _country_details_cache.set(normalized, value, ttl_seconds=_negative_cache_ttl_seconds)
    return value
