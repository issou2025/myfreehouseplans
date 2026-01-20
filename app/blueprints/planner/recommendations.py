from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .logic import FitAnalysis, OrientationResult


@dataclass(frozen=True)
class Recommendation:
    title: str
    status: str  # 'comfortable' | 'tight' | 'not_suitable'
    summary: str
    bullets: List[str]
    tip: Optional[str] = None


def _layout_label(r: OrientationResult) -> str:
    return 'Rotate it (90°)' if r.rotated else 'Keep it as-is'


def build_recommendation(analysis: FitAnalysis) -> Recommendation:
    best = analysis.best
    other = analysis.other

    if best.verdict == 'comfortable':
        title = '✅ Comfortable'
        summary = best.reason
    elif best.verdict == 'tight':
        title = '⚠️ Possible, but tight'
        summary = best.reason
    else:
        title = '❌ Not recommended'
        summary = best.reason

    bullets: List[str] = []

    # Orientation advice
    if best.verdict != other.verdict:
        if best.rotated:
            bullets.append('Good news: rotating the item makes this room feel easier to use.')
        else:
            bullets.append('Keeping the item as-is works better than rotating it in this room.')
    else:
        # Same verdict; still mention if rotation helps a bit
        if other.occupancy_ratio + 0.02 < best.occupancy_ratio:
            bullets.append('Rotation can make the room feel a little more open.')

    bullets.append(f"Suggested placement: {_layout_label(best)}.")

    # Friendly, practical hints
    if best.verdict == 'tight':
        bullets.append('If it feels cramped, consider a slightly smaller option (shorter or less deep).')
        bullets.append('Try placing it against a wall to free up the middle of the room.')

    if best.verdict == 'not_suitable':
        bullets.append('A smaller item will make the room feel much more comfortable.')
        bullets.append('If the door opens into the room, keep that corner open so you can enter easily.')

    tip = None
    if best.verdict != 'comfortable' and analysis.room.preferred_walkway_cm:
        tip = 'For narrow spaces, aim to keep a clear walking path from one end to the other.'

    return Recommendation(
        title=title,
        status=best.verdict,
        summary=summary,
        bullets=bullets,
        tip=tip,
    )
