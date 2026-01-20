from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .data import RoomType
from .logic import RoomQualityResult


@dataclass(frozen=True)
class Recommendation:
    status: str  # ok | warning | not_ok
    verdict: str  # Comfortable | Acceptable but tight | Not recommended

    daily_life: str
    room_recommendations: List[str]
    pro_advice: str

    seo_line: str
    share_line: str


def _comfort_phrase(status: str) -> str:
    if status == 'ok':
        return 'comfortable for daily use'
    if status == 'warning':
        return 'acceptable but tight for daily use'
    return 'not recommended for long-term use'


def build_recommendation(*, room: RoomType, result: RoomQualityResult) -> Recommendation:
    status = result.status
    verdict = result.verdict

    # Daily-life interpretation (room-specific, human, no jargon)
    if room.slug == 'kitchen':
        if status == 'ok':
            daily = 'This kitchen size should feel comfortable for daily use. Cooking and moving around should feel natural, not stressful.'
        elif status == 'warning':
            daily = 'This kitchen size is acceptable but tight for daily use. It can work, but the space may feel busy when more than one person is cooking.'
        else:
            daily = 'This kitchen size is not recommended for long-term use. Daily cooking is likely to feel uncomfortable in this space.'

        recs = [
            'If it feels tight, keep the layout simple so the middle of the room stays open.',
            'If you use multiple appliances, aim for a setup that feels easy to move through when something is open.',
        ]

    elif room.slug in {'bedroom', 'master-bedroom', 'children-room'}:
        if status == 'ok':
            daily = 'This room size should feel comfortable for daily use. It’s likely to feel calm and easy to live in.'
        elif status == 'warning':
            daily = 'This room size is acceptable but tight for daily use. You’ll probably feel it most when moving around furniture and storage.'
        else:
            daily = 'This room size is not recommended for long-term use. Over time, daily movement may feel uncomfortable in this setup.'

        recs = [
            'Keep the walking space around the bed feeling easy — it makes mornings and nights smoother.',
            'If it’s tight, choose slimmer storage and avoid filling every corner.',
        ]

    elif room.slug == 'living-room':
        if status == 'ok':
            daily = 'This living room size should feel comfortable for daily use. It should stay open and social, with easy movement for guests.'
        elif status == 'warning':
            daily = 'This living room size is acceptable but tight for daily use. It will work, but the room may feel less open when people move around.'
        else:
            daily = 'This living room size is not recommended for long-term use. The space may feel crowded and less relaxing day-to-day.'

        recs = [
            'If it’s tight, pick one “main” seating piece and keep the rest minimal.',
            'Aim for a layout that still feels open when people are walking through the room.',
        ]

    elif room.slug == 'bathroom':
        if status == 'ok':
            daily = 'This bathroom size should feel comfortable for daily use. It should be easy to move and use the space without awkward shuffling.'
        elif status == 'warning':
            daily = 'This bathroom size is acceptable but tight for daily use. It may feel a bit cramped when turning or reaching for things.'
        else:
            daily = 'This bathroom size is not recommended for long-term use. Daily use may feel uncomfortable in this setup.'

        recs = [
            'If it’s tight, keep the layout simple and avoid oversized fixtures.',
            'Focus on what you do every day (shower, dry off, reach storage) and keep that feeling easy.',
        ]

    elif room.slug == 'wc':
        if status == 'ok':
            daily = 'This WC size should feel comfortable for daily use.'
        elif status == 'warning':
            daily = 'This WC size is acceptable but tight for daily use. It can work, but it may feel a bit close when turning or closing the door.'
        else:
            daily = 'This WC size is not recommended for long-term use. It may feel uncomfortable to use every day.'

        recs = [
            'If it’s tight, keep the room uncluttered so it feels easier to use.',
            'A simple layout usually feels better than trying to add too much.',
        ]

    elif room.slug == 'office':
        if status == 'ok':
            daily = 'This office size should feel comfortable for daily use. Sitting down, moving your chair, and focusing should feel easy.'
        elif status == 'warning':
            daily = 'This office size is acceptable but tight for daily use. It will work, but you may notice tightness when moving your chair or accessing storage.'
        else:
            daily = 'This office size is not recommended for long-term use. Long work sessions may feel uncomfortable in this space.'

        recs = [
            'If it’s tight, a slimmer desk or wall placement is often the best quick improvement.',
            'Try to keep the room feeling uncluttered — it helps focus.',
        ]

    elif room.slug == 'garage':
        if status == 'ok':
            daily = 'This garage size should feel comfortable for daily use. You should be able to park and still use storage without constant squeezing.'
        elif status == 'warning':
            daily = 'This garage size is acceptable but tight for daily use. It can work, but access and storage may feel tight.'
        else:
            daily = 'This garage size is not recommended for long-term use. Daily access may feel uncomfortable in this setup.'

        recs = [
            'If it’s tight, keep storage to one side so the main path stays clear.',
            'Aim for a setup where you can get in and out without hassle.',
        ]

    else:
        if status == 'ok':
            daily = f"This {room.label.lower()} size should feel comfortable for daily use."
        elif status == 'warning':
            daily = f"This {room.label.lower()} size is acceptable but tight for daily use."
        else:
            daily = f"This {room.label.lower()} size is not recommended for long-term use."

        recs = [
            'If it feels tight, try a simpler layout and test again.',
            'A small change can create a better, more comfortable feel.',
        ]

    # Shape note (kept human)
    if result.shape_note:
        recs = [result.shape_note] + recs

    pro = (
        'If you’re unsure, try one more room size and compare — it’s the fastest way to find a better option.'
        if status != 'ok'
        else 'If this feels right, save it and move to the next room — consistency makes a home feel great.'
    )

    seo_line = (
        f"Room size check for {room.label.lower()}: { _comfort_phrase(status) }. "
        f"Try another size for a better layout option if needed."
    )

    share_line = (
        f"My {room.label.lower()} size check: {verdict} ({_comfort_phrase(status)}). "
        f"Want to test yours in seconds?"
    )

    return Recommendation(
        status=status,
        verdict=verdict,
        daily_life=daily,
        room_recommendations=recs,
        pro_advice=pro,
        seo_line=seo_line,
        share_line=share_line,
    )
