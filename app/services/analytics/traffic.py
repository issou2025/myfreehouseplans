"""Traffic classification helpers.

Goals:
- Identify obvious attacks/scans early.
- Classify SEO bots vs generic bots vs humans.
- Prefer "observe" to blocking, except for clear probe paths.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrafficClassification:
    traffic_type: str  # human | bot | attack
    is_search_bot: bool = False


_ATTACK_PATH_EXACT = {
    '/xmlrpc.php',
    '/wp-login.php',
    '/wp-signup.php',
    '/wp-cron.php',
    '/index.php',
    '/.env',
}

_ATTACK_PATH_PREFIXES = (
    '/wp-admin',
    '/wp-includes',
    '/wp-content',
    '/wp-json',
    '/wordpress',
    '/phpmyadmin',
    '/.git',
    '/cgi-bin',
)

_ATTACK_PATH_SUBSTRINGS = (
    'sqlmap',
    'phpunit',
)


_SEARCH_BOT_UA_TOKENS = (
    # Google
    'googlebot',
    'google-extended',
    'adsbot-google',
    'apis-google',
    'mediapartners-google',
    # Bing
    'bingbot',
    'msnbot',
    # DuckDuckGo
    'duckduckbot',
    # Yahoo
    'slurp',
    # Yandex (optional)
    'yandexbot',
    # Meta / social
    'facebookexternalhit',
    'facebot',
    'twitterbot',
    'linkedinbot',
    'pinterestbot',
)

_GENERIC_BOT_UA_TOKENS = (
    'bot',
    'crawler',
    'spider',
    'scrapy',
    'httpclient',
    'python-requests',
    'urllib',
    'wget',
    'curl',
    'libwww-perl',
    'java/',
    'okhttp',
)


def is_obvious_attack_path(path: str) -> bool:
    p = (path or '/').strip().lower() or '/'
    if p in _ATTACK_PATH_EXACT:
        return True
    if p.startswith(_ATTACK_PATH_PREFIXES):
        return True
    return any(s in p for s in _ATTACK_PATH_SUBSTRINGS)


def classify_traffic(*, path: str, user_agent: str) -> TrafficClassification:
    ua = (user_agent or '').lower()

    # Classify bots by UA.
    is_search = any(tok in ua for tok in _SEARCH_BOT_UA_TOKENS)
    if is_search:
        return TrafficClassification('bot', is_search_bot=True)

    is_generic_bot = any(tok in ua for tok in _GENERIC_BOT_UA_TOKENS)
    if is_generic_bot:
        return TrafficClassification('bot', is_search_bot=False)

    return TrafficClassification('human', is_search_bot=False)
