from __future__ import annotations

from dataclasses import dataclass

from app.blueprints.room_checker.data import RoomType
from app.blueprints.room_checker.logic import RoomQualityResult


@dataclass(frozen=True)
class IntentRecommendation:
    status: str  # ok | warning | not_ok
    verdict: str

    daily_life: str
    room_recommendations: list[str]
    pro_advice: str

    seo_line: str


def _comfort_phrase(status: str) -> str:
    if status == 'ok':
        return 'comfortable for daily use'
    if status == 'warning':
        return 'acceptable but tight for daily use'
    return 'not recommended for long-term use'


def _intent_labels(intent: str) -> tuple[str, str]:
    if intent == 'circulation':
        return 'Circulation', 'movement comfort'
    if intent == 'comfort-check':
        return 'Comfort check', 'overall comfort'
    return 'Room size', 'room size comfort'


def build_intent_recommendation(*, intent: str, room: RoomType, result: RoomQualityResult) -> IntentRecommendation:
    status = result.status
    verdict = result.verdict

    intent_title, intent_focus = _intent_labels(intent)

    # Core daily-life message (human, reassuring, non-technical)
    if intent == 'circulation':
        if status == 'ok':
            daily = 'Daily movement should feel easy here. Walking around and passing through won’t feel stressful.'
        elif status == 'warning':
            daily = 'Daily movement will work, but it may feel tight in everyday life — especially when more than one person is moving through.'
        else:
            daily = 'Daily movement is likely to feel uncomfortable here. Passing through and turning around may feel tight long-term.'

        recs = [
            'If it feels tight, keep the center of the room clear — that’s what makes movement feel easy.',
            'Avoid bulky pieces in the main walking path. A simpler layout often feels much better.',
        ]

    elif intent == 'comfort-check':
        if status == 'ok':
            daily = 'This room should feel comfortable in everyday use — easy to live in, not just “okay on paper”.'
        elif status == 'warning':
            daily = 'This room can work, but it may feel tight for daily life. Small layout choices will make a big difference.'
        else:
            daily = 'This room is not recommended for long-term daily comfort. It may feel restrictive over time.'

        recs = [
            'If you can, try one slightly larger size and compare — it’s the fastest way to find a better feel.',
            'Prioritize what you do every day in this room, and keep that experience easy.',
        ]

    else:  # room-size
        if room.slug == 'kitchen':
            if status == 'ok':
                daily = 'This kitchen size should feel comfortable for daily use. Cooking and moving around should feel natural.'
            elif status == 'warning':
                daily = 'This kitchen size can work, but it may feel tight when more than one person is cooking.'
            else:
                daily = 'This kitchen size is not recommended for long-term daily comfort. Cooking may feel stressful here.'

            recs = [
                'If it feels tight, keep the layout simple so the middle stays open.',
                'Choose storage and appliances that don’t block movement when doors are open.',
            ]

        elif room.slug in {'bedroom', 'master-bedroom', 'children-room'}:
            if status == 'ok':
                daily = 'This room size should feel comfortable for daily use. It’s likely to feel calm and easy to live in.'
            elif status == 'warning':
                daily = 'This room size can work, but it may feel tight around furniture and storage.'
            else:
                daily = 'This room size is not recommended for long-term daily comfort. Movement may feel uncomfortable here.'

            recs = [
                'Keep walking space around the bed feeling easy — it changes daily life.',
                'If it’s tight, use slimmer storage and avoid filling every corner.',
            ]

        elif room.slug == 'living-room':
            if status == 'ok':
                daily = 'This living room size should feel comfortable for daily use. It should stay open and social.'
            elif status == 'warning':
                daily = 'This living room can work, but it may feel tight when people move around.'
            else:
                daily = 'This living room size is not recommended for long-term daily comfort. The room may feel crowded.'

            recs = [
                'If it’s tight, keep one “main” seating piece and stay minimal with extras.',
                'Aim for a layout that still feels open when people walk through.',
            ]

        else:
            if status == 'ok':
                daily = f"This {room.label.lower()} size should feel comfortable for daily use."
            elif status == 'warning':
                daily = f"This {room.label.lower()} size can work, but it may feel tight in everyday life."
            else:
                daily = f"This {room.label.lower()} size is not recommended for long-term daily comfort."

            recs = [
                'If it feels tight, try a simpler layout and test again.',
                'A small change can create a better, more comfortable feel.',
            ]

    # Shape note (kept human, never technical)
    if result.shape_note:
        recs = [result.shape_note] + recs

    # Pro advice: always suggests next action
    if status == 'ok':
        pro = 'If this feels right, check furniture fit next — that’s how plans become real life.'
    else:
        pro = 'Try one more size and compare. In real planning, comparisons beat guesswork.'

    seo_line = (
        f"{room.label} {intent_title.lower()}: {verdict} ({_comfort_phrase(status)}). "
        f"Space planning before construction: check {intent_focus} in seconds."
    )

    return IntentRecommendation(
        status=status,
        verdict=verdict,
        daily_life=daily,
        room_recommendations=recs,
        pro_advice=pro,
        seo_line=seo_line,
    )
