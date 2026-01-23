from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from flask import url_for

from app.utils.article_extras import load_article_extras


@dataclass(frozen=True)
class ArticleLink:
    slug: str
    heading: str
    anchor: str

    @property
    def href(self) -> str:
        return url_for('blog.detail', slug=self.slug)


@dataclass(frozen=True)
class ExperienceLink:
    heading: str
    body: str
    cta: str
    href: str


@dataclass(frozen=True)
class ExperienceDefinition:
    key: str
    label: str
    description: str
    href: str
    article_heading: str
    article_anchor: str
    article_cta: str
    article_body: str


def _experience_definitions() -> dict[str, ExperienceDefinition]:
    return {
        'room-size': ExperienceDefinition(
            key='room-size',
            label='Room size comfort',
            description='Check if a room feels comfortable for daily life.',
            href=url_for('space_planner.room_size'),
            article_heading='Why this recommendation?',
            article_anchor='Learn how room size comfort is estimated (in plain language)',
            article_cta='Check room size comfort',
            article_body='Get a clear comfort result (comfortable / tight / not recommended).',
        ),
        'room-size:bedroom': ExperienceDefinition(
            key='room-size:bedroom',
            label='Bedroom comfort check',
            description='See if sleeping and moving around will feel comfortable.',
            href=url_for('space_planner.room_size', room='bedroom'),
            article_heading='Why this recommendation?',
            article_anchor='Bedroom size guide: what feels comfortable for sleeping',
            article_cta='Check bedroom comfort',
            article_body='Check if your bedroom will feel comfortable for sleeping and daily life.',
        ),
        'room-size:kitchen': ExperienceDefinition(
            key='room-size:kitchen',
            label='Kitchen comfort check',
            description='See if daily cooking will feel comfortable.',
            href=url_for('space_planner.room_size', room='kitchen'),
            article_heading='Why this recommendation?',
            article_anchor='Kitchen comfort guide: why cooking can feel tight',
            article_cta='Check kitchen comfort',
            article_body='See if daily cooking and moving around will feel comfortable.',
        ),
        'room-size:living-room': ExperienceDefinition(
            key='room-size:living-room',
            label='Living room comfort check',
            description='See if the space feels open for daily living.',
            href=url_for('space_planner.room_size', room='living-room'),
            article_heading='Why this recommendation?',
            article_anchor='Living room comfort guide: what feels open in daily life',
            article_cta='Check living room comfort',
            article_body='See if the space will feel open and easy for daily living.',
        ),
        'circulation': ExperienceDefinition(
            key='circulation',
            label='Circulation comfort',
            description='Check if daily movement will feel easy or tight.',
            href=url_for('space_planner.circulation'),
            article_heading='Why this recommendation?',
            article_anchor='Learn how movement comfort is estimated (in plain language)',
            article_cta='Check circulation comfort',
            article_body='See if daily movement will feel easy or tight.',
        ),
        'comfort-check': ExperienceDefinition(
            key='comfort-check',
            label='Overall comfort check',
            description='Get a clear day‑to‑day comfort summary.',
            href=url_for('space_planner.comfort_check'),
            article_heading='Why this recommendation?',
            article_anchor='Understand the comfort summary (and what to do next)',
            article_cta='Run a comfort check',
            article_body='Get an overall day‑to‑day comfort summary with a next step.',
        ),
        'furniture-fit': ExperienceDefinition(
            key='furniture-fit',
            label='Furniture fit',
            description='Check if furniture and appliances will feel comfortable in real life.',
            href=url_for('space_planner.furniture_fit'),
            article_heading='Learn how this works',
            article_anchor='Furniture fit explained: why some layouts feel tight',
            article_cta='Check furniture fit',
            article_body='Check if furniture and appliances will feel comfortable in real life.',
        ),
        'house-area-calculator': ExperienceDefinition(
            key='house-area-calculator',
            label='Home Space Decision Assistant',
            description='Plan home size decisions with room-by-room programs, circulation, and land fit.',
            href=url_for('area_calculator.index'),
            article_heading='Why this recommendation?',
            article_anchor='Home space decision assistant: bedrooms, living space, circulation',
            article_cta='Plan your home space',
            article_body='Get a room-by-room breakdown with net and gross area totals.',
        ),
    }


def get_experience_options() -> list[dict[str, str]]:
    defs = _experience_definitions().values()
    return [{'key': d.key, 'label': d.label} for d in defs]


def get_search_experiences() -> list[dict[str, str]]:
    items = [
        {'title': d.label, 'summary': d.description, 'url': d.href}
        for d in _experience_definitions().values()
    ]

    # Add room-specific entries for discoverability
    try:
        from app.blueprints.room_checker.data import ROOMS as SIZE_ROOMS
        for r in SIZE_ROOMS.values():
            items.append({
                'title': f"{r.label} space planner",
                'summary': f"Plan {r.label.lower()} comfort and daily use.",
                'url': url_for('space_planner.room', room_slug=r.slug),
            })
            items.append({
                'title': f"{r.label} furniture fit",
                'summary': f"Check if furniture feels comfortable in a {r.label.lower()}.",
                'url': url_for('planner.room', room_slug=r.slug),
            })
    except Exception:
        pass

    return items


def _experience_key_for_intent(intent: str, room_slug: Optional[str]) -> str:
    intent = (intent or '').strip().lower()
    room_slug = (room_slug or '').strip().lower() or None
    if intent == 'room-size' and room_slug:
        if room_slug in {'master-bedroom', 'children-room'}:
            room_slug = 'bedroom'
        return f"room-size:{room_slug}"
    return intent


def _published_slug(slug: str) -> bool:
    try:
        from app.models import BlogPost
        return BlogPost.query.filter_by(slug=slug, status=BlogPost.STATUS_PUBLISHED).first() is not None
    except Exception:
        return False


def _find_article_by_experience_key(key: str) -> Optional[str]:
    """Return the slug of the first published article linked to this experience key (extras-based)."""

    try:
        from app.models import BlogPost
        posts = BlogPost.query.filter_by(status=BlogPost.STATUS_PUBLISHED).all()
    except Exception:
        return None

    for post in posts:
        try:
            extras = load_article_extras(slug=post.slug, post_id=post.id)
            if (extras or {}).get('experience_key') == key:
                return post.slug
        except Exception:
            continue
    return None


_DEFAULT_ARTICLE_BY_EXPERIENCE: dict[str, str] = {
    'room-size': 'room-size-made-simple',
    'room-size:bedroom': 'bedroom-size-guide',
    'room-size:kitchen': 'kitchen-space-cooking-comfort',
    'room-size:living-room': 'living-room-comfort-guide',
    'circulation': 'circulation-made-simple',
    'comfort-check': 'room-comfort-made-simple',
    'furniture-fit': 'furniture-fit-explained',
}


def article_for_space_planner(*, intent: str, room_slug: Optional[str]) -> Optional[ArticleLink]:
    key = _experience_key_for_intent(intent, room_slug)
    defs = _experience_definitions()
    definition = defs.get(key) or defs.get(intent)
    if not definition:
        return None

    # Admin override: article extras can declare which experience it explains.
    admin_slug = _find_article_by_experience_key(key)
    if admin_slug and _published_slug(admin_slug):
        return ArticleLink(slug=admin_slug, heading=definition.article_heading, anchor=definition.article_anchor)

    # Fallback: static mapping if the article exists.
    static_slug = _DEFAULT_ARTICLE_BY_EXPERIENCE.get(key)
    if static_slug and _published_slug(static_slug):
        return ArticleLink(slug=static_slug, heading=definition.article_heading, anchor=definition.article_anchor)

    return None


def experience_for_article(*, slug: str, extras: Optional[dict]) -> Optional[ExperienceLink]:
    """Map a blog article back to a single Space Planner experience.

    If extras define `experience_key`, that wins. Otherwise fall back to the known static mapping.
    """

    slug = (slug or '').strip().lower()
    extras = extras or {}
    defs = _experience_definitions()

    key = (extras.get('experience_key') or '').strip().lower()
    if key and key in defs:
        d = defs[key]
        return ExperienceLink(heading=d.article_heading, body=d.article_body, cta=d.article_cta, href=d.href)

    # Reverse lookup from static mapping
    for exp_key, mapped_slug in _DEFAULT_ARTICLE_BY_EXPERIENCE.items():
        if mapped_slug == slug and exp_key in defs:
            d = defs[exp_key]
            return ExperienceLink(heading=d.article_heading, body=d.article_body, cta=d.article_cta, href=d.href)

    return None


def room_guidance_line(room_slug: str, room_label: str) -> str:
    slug = (room_slug or '').strip().lower()
    label = (room_label or 'this room').strip()

    if slug in {'bedroom', 'master-bedroom', 'children-room'}:
        return 'Helps you see if sleeping and moving around will feel comfortable.'
    if slug == 'kitchen':
        return 'Helps you see if daily cooking and moving around will feel comfortable.'
    if slug == 'living-room':
        return 'Helps you see if the space feels open for daily living.'
    if slug in {'bathroom', 'wc'}:
        return 'Helps you see if daily use will feel easy or tight.'
    if slug == 'office':
        return 'Helps you see if working and moving around will feel comfortable.'
    if slug == 'garage':
        return 'Helps you see if parking and storage will feel usable day-to-day.'

    return f"Helps you see if {label.lower()} will feel comfortable in daily life."