"""Simple user-agent based device detection."""

from __future__ import annotations


def detect_device_type(user_agent: str) -> str:
    """Return device category: desktop | mobile | tablet | bot | unknown."""
    ua = (user_agent or '').lower()

    if not ua:
        return 'unknown'

    bot_tokens = ('bot', 'crawler', 'spider', 'slurp', 'bingbot', 'googlebot', 'duckduckbot')
    if any(tok in ua for tok in bot_tokens):
        return 'bot'

    tablet_tokens = ('ipad', 'tablet', 'kindle', 'silk', 'playbook')
    if any(tok in ua for tok in tablet_tokens):
        return 'tablet'

    mobile_tokens = (
        'mobi', 'iphone', 'android', 'blackberry', 'phone', 'opera mini', 'iemobile', 'windows phone'
    )
    if any(tok in ua for tok in mobile_tokens):
        return 'mobile'

    return 'desktop'
