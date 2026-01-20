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
    note: Optional[str] = None


def _orientation_label(r: OrientationResult) -> str:
    return 'Rotated (90°)' if r.rotated else 'Normal orientation'


def build_recommendation(analysis: FitAnalysis) -> Recommendation:
    best = analysis.best
    other = next((r for r in analysis.results if r.rotated != best.rotated), None)

    if best.verdict == 'comfortable':
        title = '✅ Comfortable fit'
        summary = 'The furniture fits comfortably with proper circulation.'
    elif best.verdict == 'tight':
        title = '⚠️ Possible but tight'
        summary = 'The furniture fits, but circulation is limited in at least one area.'
    else:
        title = '❌ Not suitable'
        summary = 'The furniture blocks functional movement and is not recommended for this room size.'

    bullets: List[str] = []

    # Professional circulation guidance without exposing calculations.
    bullets.append(best.clearance_note)

    if best.verdict in ('comfortable', 'tight'):
        if best.tight_axis == 'width':
            bullets.append('Circulation feels tighter across the room width; keep paths clear near doors and corners.')
        elif best.tight_axis == 'length':
            bullets.append('Circulation feels tighter along the room length; consider shifting placement to avoid pinch points.')
        else:
            bullets.append('Circulation remains balanced on both axes for typical use.')

    # Rotation insight
    if other is not None:
        if other.verdict != best.verdict:
            if best.rotated:
                bullets.append('Rotating the furniture improves usability in this room.')
            else:
                bullets.append('Rotation does not improve usability for this room.')
        else:
            # Same verdict: mention if one has visibly more breathing room.
            best_min = min(best.remaining_length_cm, best.remaining_width_cm)
            other_min = min(other.remaining_length_cm, other.remaining_width_cm)
            if other_min > best_min + 10:
                bullets.append('Consider rotating the furniture; it provides slightly better circulation margins.')

    bullets.append(f"Recommended layout: {_orientation_label(best)}.")

    note = None
    if best.verdict == 'not_suitable' and other is not None and other.verdict in ('tight', 'comfortable'):
        note = 'Tip: Try swapping length/width inputs if your measurement orientation is reversed.'

    return Recommendation(
        title=title,
        status=best.verdict,
        summary=summary,
        bullets=bullets,
        note=note,
    )
