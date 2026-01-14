"""Fail-safe GeoIP lookup utilities (read-only)."""

from __future__ import annotations

import os
from functools import lru_cache

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


@lru_cache(maxsize=2048)
def get_country_for_ip(ip: str | None) -> str:
    """Return country name for IP (fail-safe, read-only)."""
    if not ip:
        return 'Unknown country'
    if _reader is None:
        return 'Unknown country'
    try:
        response = _reader.country(ip)
        return response.country.name or 'Unknown country'
    except AddressNotFoundError:
        return 'Unknown country'
    except Exception:
        return 'Unknown country'
