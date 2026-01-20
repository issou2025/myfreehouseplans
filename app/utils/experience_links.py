from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from flask import url_for


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


# NOTE: This is deliberately code-only (no DB relations). Slugs should match existing blog posts.
# If a slug does not exist yet, the UI will still render a clean link; you can publish the article
# later with the same slug.


_GENERIC_INTENT_ARTICLES: dict[str, ArticleLink] = {
    'room-size': ArticleLink(
        slug='room-size-made-simple',
        heading='Why this recommendation?',
        anchor='Learn how room size comfort is estimated (in plain language)',
    ),
    'circulation': ArticleLink(
        slug='circulation-made-simple',
        heading='Why this recommendation?',
        anchor='Learn how movement comfort is estimated (in plain language)',
    ),
    'comfort-check': ArticleLink(
        slug='room-comfort-made-simple',
        heading='Why this recommendation?',
        anchor='Understand the comfort summary (and what to do next)',
    ),
    'furniture-fit': ArticleLink(
        slug='furniture-fit-explained',
        heading='Learn how this works',
        anchor='Furniture fit explained: why some layouts feel tight',
    ),
}


_ROOM_SIZE_OVERRIDES: dict[str, ArticleLink] = {
    'bedroom': ArticleLink(
        slug='bedroom-size-guide',
        heading='Why this recommendation?',
        anchor='Bedroom size guide: what feels comfortable for sleeping',
    ),
    'master-bedroom': ArticleLink(
        slug='bedroom-size-guide',
        heading='Why this recommendation?',
        anchor='Bedroom size guide: what feels comfortable for sleeping',
    ),
    'children-room': ArticleLink(
        slug='bedroom-size-guide',
        heading='Why this recommendation?',
        anchor='Bedroom size guide: what feels comfortable for sleeping',
    ),
    'kitchen': ArticleLink(
        slug='kitchen-space-cooking-comfort',
        heading='Why this recommendation?',
        anchor='Kitchen comfort guide: why cooking can feel tight',
    ),
    'living-room': ArticleLink(
        slug='living-room-comfort-guide',
        heading='Why this recommendation?',
        anchor='Living room comfort guide: what feels open in daily life',
    ),
}


def article_for_space_planner(*, intent: str, room_slug: Optional[str]) -> Optional[ArticleLink]:
    intent = (intent or '').strip().lower()
    room_slug = (room_slug or '').strip().lower() or None

    if intent == 'room-size' and room_slug and room_slug in _ROOM_SIZE_OVERRIDES:
        return _ROOM_SIZE_OVERRIDES[room_slug]

    return _GENERIC_INTENT_ARTICLES.get(intent)


def experience_for_article_slug(slug: str) -> Optional[ExperienceLink]:
    """Map a blog article slug back to one primary Space Planner experience.

    This is the reciprocal link (article → experience). Keep it simple: one article → one CTA.
    """

    slug = (slug or '').strip().lower()

    # Room-size guides
    if slug in {'bedroom-size-guide'}:
        return ExperienceLink(
            heading='Try it with your bedroom',
            body='Check if your bedroom will feel comfortable for sleeping and daily life.',
            cta='Check bedroom comfort',
            href=url_for('space_planner.room_size', room='bedroom'),
        )

    if slug in {'kitchen-space-cooking-comfort'}:
        return ExperienceLink(
            heading='Try it with your kitchen',
            body='See if daily cooking and moving around will feel comfortable.',
            cta='Check kitchen comfort',
            href=url_for('space_planner.room_size', room='kitchen'),
        )

    if slug in {'living-room-comfort-guide'}:
        return ExperienceLink(
            heading='Try it with your living room',
            body='See if the space will feel open and easy for daily living.',
            cta='Check living room comfort',
            href=url_for('space_planner.room_size', room='living-room'),
        )

    # Generic intent articles
    if slug == 'room-size-made-simple':
        return ExperienceLink(
            heading='Try it with your room',
            body='Get a clear comfort result (comfortable / tight / not recommended).',
            cta='Check room size comfort',
            href=url_for('space_planner.room_size'),
        )

    if slug == 'circulation-made-simple':
        return ExperienceLink(
            heading='Try it with your room',
            body='See if daily movement will feel easy or tight.',
            cta='Check circulation comfort',
            href=url_for('space_planner.circulation'),
        )

    if slug == 'room-comfort-made-simple':
        return ExperienceLink(
            heading='Try it with your room',
            body='Get an overall day‑to‑day comfort summary with a next step.',
            cta='Run a comfort check',
            href=url_for('space_planner.comfort_check'),
        )

    if slug == 'furniture-fit-explained':
        return ExperienceLink(
            heading='Try it with your room',
            body='Check if furniture and appliances will feel comfortable in real life.',
            cta='Check furniture fit',
            href=url_for('space_planner.furniture_fit'),
        )

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